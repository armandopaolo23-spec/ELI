import requests
import json
from blackboard_auth import BlackboardAuth

from logger import get_logger

log = get_logger(__name__)


class BlackboardAPI:
    def __init__(self):
        self.auth = BlackboardAuth()
        self.base_url = "https://upn.blackboard.com"
        self.user_id = "_378679_1"  # Tu user ID de Blackboard
        self.session = requests.Session()
        self._configurar_headers()
    
    def _configurar_headers(self):
        """Headers base para todas las peticiones"""
        self.session.headers.update({
            'Host': 'upn.blackboard.com',
            'Referer': 'https://upn.blackboard.com/ultra/course',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
    
    def _cargar_cookies_en_session(self):
        """Carga cookies en la sesión de requests"""
        cookies = self.auth.obtener_cookies()
        if not cookies:
            raise Exception("No se pudieron obtener cookies")
        
        for name, value in cookies.items():
            self.session.cookies.set(name, value)
    
    def _request_con_retry(self, method, url, **kwargs):
        """Hace request con retry automático si las cookies expiran"""
        try:
            response = self.session.request(method, url, **kwargs)
            
            # Si falla por auth, renovar cookies y reintentar
            if response.status_code in [401, 403]:
                log.warning("Cookies expiradas, renovando...")
                self.auth.obtener_cookies(forzar_renovar=True)
                self._cargar_cookies_en_session()
                response = self.session.request(method, url, **kwargs)

            response.raise_for_status()
            return response
        except Exception as e:
            log.error("Error en request a Blackboard: %s", e)
            raise
    
    def listar_cursos(self):
        """Obtiene lista de cursos del usuario"""
        self._cargar_cookies_en_session()
        
        url = f"{self.base_url}/learn/api/v1/users/{self.user_id}/memberships"
        params = {
            'expand': 'course.effectiveAvailability,course.permissions,courseRole',
            'includeCount': 'true',
            'limit': '10000'
        }
        
        response = self._request_con_retry('GET', url, params=params)
        data = response.json()
        
        cursos = []
        for item in data.get('results', []):
            curso = item.get('course', {})
            cursos.append({
                'id': curso.get('id'),
                'nombre': curso.get('displayName'),
                'codigo': curso.get('displayId'),
                'disponible': curso.get('isAvailable'),
                'ultima_visita': item.get('lastAccessDate'),
                'url': curso.get('externalAccessUrl')
            })
        
        return cursos
    
    def obtener_tareas(self, curso_id):
        """Obtiene tareas pendientes de un curso (placeholder)"""
        # TODO: Investigar endpoint de assignments
        # Probablemente: /learn/api/v1/courses/{curso_id}/contents
        # o /learn/api/v1/courses/{curso_id}/gradebook/columns
        pass
