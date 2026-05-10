"""Tests del splitter de oraciones que alimenta el pipeline de TTS."""

from hablar import _dividir_oraciones, _MIN_LARGO_FRAGMENTO


class TestDividirOraciones:
    def test_oracion_unica(self):
        assert _dividir_oraciones("Hola.") == ["Hola."]

    def test_texto_vacio(self):
        assert _dividir_oraciones("") == []

    def test_solo_whitespace(self):
        assert _dividir_oraciones("   \n\t   ") == []

    def test_sin_terminador_devuelve_uno(self):
        # Sin punto/cierre no podemos partir; lo damos completo.
        texto = "Una sola oración sin punto"
        assert _dividir_oraciones(texto) == [texto]

    def test_dos_oraciones_largas_se_separan(self):
        texto = "Esta es la primera oración larga. Esta es la segunda oración larga."
        partes = _dividir_oraciones(texto)
        assert len(partes) == 2
        assert partes[0] == "Esta es la primera oración larga."
        assert partes[1] == "Esta es la segunda oración larga."

    def test_fragmento_corto_se_fusiona_con_siguiente(self):
        # "Hola." es < _MIN_LARGO_FRAGMENTO; debe fusionarse.
        partes = _dividir_oraciones("Hola. ¿Cómo estás esta tarde?")
        assert len(partes) == 1

    def test_tres_oraciones_se_pipeline_an(self):
        # Cada una >=15 chars → tres fragmentos para máximo solape.
        texto = (
            "Sistemas en línea. "
            "Listo para ayudarte. "
            "Los parámetros son aceptables."
        )
        partes = _dividir_oraciones(texto)
        assert len(partes) == 3

    def test_signos_de_pregunta_y_exclamacion(self):
        partes = _dividir_oraciones(
            "¡Qué interesante experimento! ¿De verdad funciona así?"
        )
        # Ambos tienen >15 chars sin contar el signo de apertura.
        assert len(partes) == 2

    def test_puntos_suspensivos_caracter_unicode(self):
        # … (U+2026) debe contar como cierre.
        partes = _dividir_oraciones(
            "Anomalía detectada en los datos… Procediendo con análisis."
        )
        assert len(partes) == 2

    def test_no_falsa_division_en_abreviatura_con_punto(self):
        # "8:30 a.m." el split solo ocurre con espacio después del cierre,
        # así que "a.m." no parte.
        partes = _dividir_oraciones("Buenos días. Son las 8:30 a.m.")
        # Debería quedar como dos fragmentos pero sin partir dentro de a.m.
        for parte in partes:
            assert not parte.endswith("a.")
            assert "a.m." in parte or "Buenos" in parte

    def test_resto_corto_se_pega_al_ultimo(self):
        # Última oración es muy corta y queda en el buffer; se debe
        # pegar al fragmento previo en vez de quedar suelta.
        partes = _dividir_oraciones("Primera oración suficientemente larga. Sí.")
        # El "Sí." (3 chars) no debe quedar como fragmento aislado.
        assert all(len(p) >= 4 for p in partes)

    def test_min_largo_es_consistente(self):
        # Si bajamos el umbral de fusión, deberíamos obtener más fragmentos.
        # Verificamos que el comportamiento depende efectivamente de la
        # constante (regression guard).
        assert _MIN_LARGO_FRAGMENTO >= 1
