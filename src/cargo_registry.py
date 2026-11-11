"""Прямой доступ к API crates.io без Cargo и сторонних пакетов."""

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin
from urllib.request import Request, urlopen

from src.models import Dependency, Package
from src.semver import SemVer, matches_requirement, parse_version


PAGE_SIZE = 100
REQUEST_INTERVAL = 1.0
REQUEST_TIMEOUT = 20
MIN_DELAY_SECONDS = 0.0
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR_MIN = 500
USER_AGENT = (
    "CargoDependencyGraphVisualizer/1.0 "
    "(https://github.com/Yaicehrust/Configuration-Management-pract-2)"
)


class RegistryError(RuntimeError):
    """Возникает, когда crates.io не возвращает корректные данные пакета."""


class CratesIoClient:
    """Получает сведения о пакете Cargo через публичный HTTP API crates.io."""

    def __init__(self, repository_url: str) -> None:
        """Инициализирует объект."""
        self.base_url = _api_base(repository_url)
        self._last_request = 0.0
        self._versions: dict[str, list[dict[str, object]]] = {}
        self._dependencies: dict[Package, list[Dependency]] = {}
        self._reverse: dict[str, list[Package]] = {}

    def direct_dependencies(self, package: Package) -> list[Dependency]:
        """Получает и разрешает зависимости указанной версии пакета."""
        if package in self._dependencies:
            return self._dependencies[package]
        payload = self._request_json(self._crate_url(package, "dependencies"))
        records = payload.get("dependencies")
        if not isinstance(records, list):
            raise RegistryError("Registry response has no dependencies array.")
        dependencies = [
        self._resolve_dependency(item)
        for item in records
        if isinstance(item, dict)
        and item.get("kind") in ("normal", "build", None)
]
        dependencies.sort(key=lambda item: item.package)
        self._dependencies[package] = dependencies
        return dependencies

    def package_dependencies(self, package: Package) -> list[Package]:
        """Возвращает пакеты, выбранные для прямых зависимостей."""
        return [item.package for item in self.direct_dependencies(package)]

    def reverse_dependencies(self, package: Package) -> list[Package]:
        """Возвращает пакеты, напрямую зависящие от указанного пакета."""
        if package.name in self._reverse:
            return self._reverse[package.name]
        dependents = self._load_reverse_dependencies(package.name)
        self._reverse[package.name] = dependents
        return dependents

    def _resolve_dependency(self, record: object) -> Dependency:
        """Преобразует запись API о зависимости в ребро графа."""
        if not isinstance(record, dict):
            message = "Registry returned an invalid dependency record."
            raise RegistryError(message)
        name = record.get("crate_id")
        requirement = record.get("req")
        if not isinstance(name, str) or not isinstance(requirement, str):
            raise RegistryError("Dependency record is missing crate_id or req.")
        version = self._select_version(name, requirement)
        kind = record.get("kind") or "normal"
        target = record.get("target")
        return Dependency(
            Package(name, version),
            requirement,
            str(kind),
            bool(record.get("optional", False)),
            target if isinstance(target, str) else None,
        )

    def _select_version(self, name: str, requirement: str) -> str:
        """Выбирает новейшую версию, подходящую под требование Cargo."""
        versions = self._load_versions(name)
        candidates = [
            str(item["num"])
            for item in versions
            if not item.get("yanked", False)
            and isinstance(item.get("num"), str)
            and _matches_version_safely(str(item["num"]), requirement)
        ]
        if not candidates:
            raise RegistryError(
                f"No non-yanked version of {name} matches {requirement}."
            )
        return max(candidates, key=parse_version)

    def _load_versions(self, name: str) -> list[dict[str, object]]:
        """Загружает страницы версий до получения всех записей реестра."""
        if name in self._versions:
            return self._versions[name]

        versions: list[dict[str, object]] = []
        next_page: str | None = None
        seen_pages: set[str] = set()

        while True:
            items, next_page = self._fetch_versions_page(name, next_page)
            versions.extend(items)

            if next_page is None:
                break
            if next_page in seen_pages:
                raise RegistryError(f"Repeated pagination link for {name}.")
            seen_pages.add(next_page)

        self._versions[name] = versions
        return versions
    
    def _fetch_versions_page(
        self, name: str, next_page: str | None
    ) -> tuple[list[dict[str, object]], str | None]:
        """Получает и проверяет одну страницу опубликованных версий."""
        url = self._crate_url(Package(name, "0.0.0"), "versions")
        if next_page is None:
            query = urlencode({"per_page": PAGE_SIZE})
            url = f"{url}?{query}"
        else:
            url = f"{url}{next_page}"

        payload = self._request_json(url)
        items = payload.get("versions")
        if not isinstance(items, list):
            raise RegistryError(f"Invalid versions response for {name}.")

        valid_items = [item for item in items if isinstance(item, dict)]
        meta = payload.get("meta", {})
        if not isinstance(meta, dict):
            return valid_items, None

        next_page = meta.get("next_page")
        if not isinstance(next_page, str) or not next_page:
            return valid_items, None
        if not next_page.startswith("?"):
            raise RegistryError(f"Invalid pagination link for {name}.")
        return valid_items, next_page

    

    def _load_reverse_dependencies(self, name: str) -> list[Package]:
        """Читает все страницы и выбирает версию каждого зависимого пакета."""
        dependents: dict[str, list[str]] = {}
        page = 1
        total: int | None = None
        while total is None or sum(map(len, dependents.values())) < total:
            query = urlencode({"per_page": PAGE_SIZE, "page": page})
            package = Package(name, "0.0.0")
            url = self._crate_url(package, "reverse_dependencies")
            payload = self._request_json(f"{url}?{query}")
            self._collect_reverse_page(payload, dependents)
            meta = payload.get("meta", {})
            if total is None and isinstance(meta, dict):
                value = meta.get("total")
                total = value if isinstance(value, int) else None
            records = payload.get("dependencies", [])
            if not records or len(records) < PAGE_SIZE:
                break
            page += 1
        packages = [
            Package(crate, max(versions, key=parse_version))
            for crate, versions in dependents.items()
        ]
        return sorted(packages)

    @staticmethod
    def _collect_reverse_page(
        payload: dict[str, object], collected: dict[str, list[str]]
    ) -> None:
        """Связывает записи обратных зависимостей с версиями пакетов."""
        records = payload.get("dependencies")
        versions = payload.get("versions")
        if not isinstance(records, list) or not isinstance(versions, list):
            raise RegistryError("Invalid reverse-dependencies response.")
        version_map = {
            item.get("id"): item
            for item in versions
            if isinstance(item, dict) and isinstance(item.get("id"), int)
        }
        for record in records:
            _collect_reverse_record(record, version_map, collected)

    def _crate_url(self, package: Package, suffix: str) -> str:
        """Формирует URL для пакета или его версии в API."""
        name = quote(package.name, safe="")
        version = quote(package.version, safe="")
        path = f"crates/{name}/{version}/{suffix}"
        if suffix == "versions" or suffix == "reverse_dependencies":
            path = f"crates/{name}/{suffix}"
        return urljoin(self.base_url, path)

    def _request_json(self, url: str) -> dict[str, object]:
        """Отправляет запрос с ограничением частоты и разбирает JSON-ответ."""
        self._wait_for_rate_limit()
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                raw_content = response.read()
        except HTTPError as error:
            raise _http_error(error) from error
        except URLError as error:
            raise RegistryError(f"Network error: {error.reason}") from error
        except TimeoutError as error:
            raise RegistryError("Registry request timed out.") from error
        except OSError as error:
            raise RegistryError(f"Network I/O error: {error}") from error
        try:
            content = raw_content.decode("utf-8")
        except UnicodeDecodeError as error:
            message = "Registry response is not valid UTF-8."
            raise RegistryError(message) from error
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise RegistryError("Registry returned invalid JSON.") from error
        if not isinstance(payload, dict):
            raise RegistryError("Registry JSON response must be an object.")
        return payload

    def _wait_for_rate_limit(self) -> None:
        """Ограничивает частоту запросов: не более одного в секунду."""
        now = time.monotonic()
        delay = REQUEST_INTERVAL - (now - self._last_request)
        if delay > MIN_DELAY_SECONDS:
            time.sleep(delay)
        self._last_request = time.monotonic()


def _collect_reverse_record(
    record: object,
    version_map: dict[object, dict[str, object]],
    collected: dict[str, list[str]],
) -> None:
    """Добавляет доступную версию зависимого пакета из ответа API."""
    if not isinstance(record, dict):
        return
    version = version_map.get(record.get("version_id"))
    if not isinstance(version, dict) or version.get("yanked", False):
        return
    crate = version.get("crate")
    number = version.get("num")
    if isinstance(crate, str) and isinstance(number, str):
        collected.setdefault(crate, []).append(number)


def _api_base(repository_url: str) -> str:
    """Приводит URL реестра Cargo к базовому адресу API."""
    base = repository_url.rstrip("/")
    if base.endswith("/api/v1"):
        return f"{base}/"
    return f"{base}/api/v1/"


def _matches_version_safely(version: str, requirement: str) -> bool:
    """Считает неподдерживаемые и некорректные версии неподходящими."""
    try:
        return matches_requirement(version, requirement)
    except ValueError:
        return False


def _http_error(error: HTTPError) -> RegistryError:
    """Преобразует распространённые HTTP-ошибки в понятные сообщения."""
    if error.code == HTTP_NOT_FOUND:
        message = "Package or package version was not found in crates.io."
    elif error.code == HTTP_TOO_MANY_REQUESTS:
        message = "crates.io rate limit reached; wait and try again."
    elif error.code >= HTTP_SERVER_ERROR_MIN:
        message = f"crates.io server error: HTTP {error.code}."
    else:
        message = f"crates.io request failed: HTTP {error.code}."
    return RegistryError(message)
