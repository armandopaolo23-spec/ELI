import json
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from logger import get_logger

log = get_logger(__name__)


class AulaVirtualUPN:
    """Automatiza Blackboard UPN usando Chrome WebDriver y cookies JSON."""

    BASE_URL = "https://estudiante.upn.edu.pe"

    def __init__(self, headless=False, timeout=20):
        """Inicializa el navegador Chrome y el manejador de espera.

        headless: si es True, ejecuta Chrome en modo sin cabeza.
        timeout: tiempo máximo en segundos para cargas y esperas.
        """
        opciones = Options()
        if headless:
            opciones.add_argument('--headless')
        opciones.add_argument('--no-sandbox')
        opciones.add_argument('--disable-dev-shm-usage')

        self.driver = webdriver.Chrome(options=opciones)
        self.driver.set_page_load_timeout(timeout)
        self.wait = WebDriverWait(self.driver, timeout)
        self.cookies_path = Path("upn_cookies.json")

    def cargar_cookies(self, archivo):
        """Carga cookies desde un archivo JSON y las aplica al navegador.

        archivo: ruta del archivo JSON que contiene la sesión guardada.
        """
        ruta = Path(archivo)
        if not ruta.exists():
            raise FileNotFoundError(f"No existe el archivo de cookies: {ruta}")

        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        with ruta.open("r", encoding="utf-8") as archivo_json:
            cookies = json.load(archivo_json)

        if not isinstance(cookies, list):
            raise ValueError("El archivo de cookies debe contener una lista JSON.")

        for cookie in cookies:
            cookie_saneada = {k: v for k, v in cookie.items() if k in {
                "name", "value", "path", "domain", "secure", "httpOnly", "expiry", "sameSite"
            }}

            if "sameSite" in cookie_saneada:
                same_site = cookie_saneada["sameSite"]
                if same_site not in ("Lax", "Strict", "None"):
                    cookie_saneada.pop("sameSite", None)

            try:
                self.driver.add_cookie(cookie_saneada)
            except WebDriverException:
                # Algunos navegadores rechazan cookies irrelevantes; se ignoran.
                continue

        self.driver.refresh()
        time.sleep(2)

    def guardar_cookies(self, archivo):
        """Guarda las cookies de la sesión actual en un archivo JSON.

        archivo: ruta del archivo JSON donde se guardarán las cookies.
        """
        ruta = Path(archivo)
        cookies = self.driver.get_cookies()

        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("w", encoding="utf-8") as archivo_json:
            json.dump(cookies, archivo_json, indent=2, ensure_ascii=False)

    def login_manual_y_guardar(self):
        """Abre el navegador para iniciar sesión manualmente y guarda las cookies.

        El usuario debe completar el login en la página de Blackboard UPN.
        """
        self.driver.get(self.BASE_URL)
        try:
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            pass

        log.info("Abriendo Blackboard UPN en Firefox...")
        log.info("Inicia sesión manualmente en la ventana abierta.")
        input("Cuando hayas iniciado sesión, presiona Enter para guardar las cookies: ")

        self.guardar_cookies(self.cookies_path)
        log.info("Cookies guardadas en: %s", self.cookies_path)

    def _verificar_sesion(self):
        """Verifica si la sesión parece estar activa revisando el estado de la página."""
        url_actual = self.driver.current_url.lower()
        if "login" in url_actual or "signin" in url_actual:
            return False

        try:
            self.driver.find_element(By.CSS_SELECTOR, "body")
        except NoSuchElementException:
            return False

        return True

    def listar_cursos(self):
        """Devuelve una lista de cursos del estudiante en Blackboard UPN."""
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        if not self._verificar_sesion():
            raise RuntimeError("No se detectó una sesión activa. Carga cookies o inicia sesión manualmente.")

        curso_selectores = [
            "a[href*='course_id=']",
            "a[href*='/webapps/blackboard/execute/courseMain?']",
            "a[class*='course']",
            "a[href*='course']",
        ]

        cursos = []
        vistos = set()
        for selector in curso_selectores:
            for elemento in self.driver.find_elements(By.CSS_SELECTOR, selector):
                titulo = elemento.text.strip()
                enlace = elemento.get_attribute("href")
                if titulo and enlace:
                    clave = (titulo, enlace)
                    if clave not in vistos:
                        vistos.add(clave)
                        cursos.append({"titulo": titulo, "url": enlace})

        if not cursos:
            cursos = self._buscar_cursos_por_texto()

        return cursos

    def _buscar_cursos_por_texto(self):
        """Busca cursos usando texto que contenga 'curso' o 'course'."""
        cursos = []
        vistos = set()
        xpath = (
            "//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'curso')]"
            "|//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'course')]"
        )
        for elemento in self.driver.find_elements(By.XPATH, xpath):
            titulo = elemento.text.strip()
            enlace = elemento.get_attribute("href")
            if titulo and enlace:
                clave = (titulo, enlace)
                if clave not in vistos:
                    vistos.add(clave)
                    cursos.append({"titulo": titulo, "url": enlace})
        return cursos

    def obtener_tareas_pendientes(self):
        """Devuelve una lista de tareas pendientes sin entregar."""
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        if not self._verificar_sesion():
            raise RuntimeError("No se detectó una sesión activa. Carga cookies o inicia sesión manualmente.")

        tareas = []
        vistos = set()

        xpaths = [
            "//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'tarea')]",
            "//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'entrega')]",
            "//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'assignment')]",
            "//div[contains(translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'todo')]//li",
            "//div[contains(translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'todo')]//li",
            "//table//tr[.//td[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sin entregar') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'no entregado') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'pending')]]"
        ]

        for xpath in xpaths:
            for elemento in self.driver.find_elements(By.XPATH, xpath):
                texto = elemento.text.strip()
                enlace = elemento.get_attribute("href") if elemento.tag_name.lower() == "a" else None
                if not texto:
                    continue

                clave = (texto, enlace)
                if clave in vistos:
                    continue

                vistos.add(clave)
                tarea = {"descripcion": texto}
                if enlace:
                    tarea["url"] = enlace
                tareas.append(tarea)

        return tareas

    def debug_cursos(self):
        """Inspecciona la página de cursos para identificar selectores correctos."""
        log.info("🔍 DEBUG: Navegando a la página de cursos...")

        self.driver.get(self.BASE_URL)
        time.sleep(10)
        self.driver.save_screenshot("blackboard_pagina.png")
        log.info("📸 Screenshot guardado: blackboard_pagina.png")

        try:
            sidebar_cursos = self.driver.find_element(
                By.XPATH,
                "//p[contains(text(), 'Cursos')] | //a[contains(text(), 'Cursos')]"
            )
            sidebar_cursos.click()
            log.info("✅ Click en 'Cursos' exitoso")
            time.sleep(5)
            self.driver.save_screenshot("blackboard_despues_click.png")
        except Exception as e:
            log.warning("No se pudo hacer click en Cursos: %s", e)

        with open("blackboard_cursos_debug.html", "w", encoding="utf-8") as f:
            f.write(self.driver.page_source)
        log.info("📄 HTML guardado en: blackboard_cursos_debug.html")

        log.info("📋 Buscando links de cursos...")
        links = self.driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            texto = link.text.strip()
            href = link.get_attribute("href")
            if texto and href and ("curso" in texto.lower() or "course" in href.lower()):
                log.debug("link curso → texto=%r url=%s clase=%s",
                          texto, href, link.get_attribute("class"))

        log.info("✅ Debug completado. Revisa blackboard_cursos_debug.html")
        input("Presiona Enter cuando hayas revisado Chrome...")

    def cerrar(self):
        """Cierra el navegador y libera los recursos de WebDriver."""
        try:
            self.driver.quit()
        except WebDriverException:
            pass


def main():
    """Ejemplo de uso de AulaVirtualUPN para pruebas rápidas."""
    aula = AulaVirtualUPN(headless=False)
    archivo_cookies = Path("upn_cookies.json")

    try:
        if archivo_cookies.exists():
            print(f"Cargando cookies desde {archivo_cookies}...")
            aula.cargar_cookies(archivo_cookies)
        else:
            print("No se encontró archivo de cookies. Se requiere login manual.")
            aula.login_manual_y_guardar()

        aula.debug_cursos()

    except Exception as error:
        print(f"Error: {error}")
    finally:
        aula.cerrar()


if __name__ == "__main__":
    main()
