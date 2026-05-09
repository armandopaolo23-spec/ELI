# ============================================================
# interfaz.py — Interfaz visual estilo JARVIS para Eli
# HUD con anillo animado, estados visuales y log de conversación
# Corre en un hilo separado para no bloquear el loop de voz
# ============================================================

import tkinter as tk   # Librería gráfica incluida con Python
import threading       # Para correr la interfaz en un hilo separado
import math            # Para cálculos de seno/coseno (animaciones circulares)
import time            # Para controlar la velocidad de las animaciones

# --- Colores del HUD ---
# Definimos todos los colores en un solo lugar para fácil personalización.
NEGRO = "#000000"
AZUL_ELECTRICO = "#00A8FF"
CYAN = "#00FFFF"
AZUL_TENUE = "#003355"       # Azul oscuro para el estado de espera
AZUL_MEDIO = "#005588"       # Para detalles secundarios
BLANCO = "#FFFFFF"
GRIS = "#556677"             # Para texto secundario


class InterfazEli:
    """
    Ventana estilo HUD de JARVIS con anillo animado y log de conversación.

    Estados posibles:
        "espera"     — Anillo tenue, quieto. Eli no hace nada.
        "escuchando" — Anillo pulsa en azul. Eli espera que hables.
        "pensando"   — Anillo gira. Eli procesa con Ollama.
        "hablando"   — Anillo pulsa rápido en cyan. Eli responde.
    """

    def __init__(self):
        # Estado actual de Eli. Controla la animación del anillo.
        self.estado = "espera"

        # Variable para controlar el bucle de animación.
        # Cuando se pone en False, la animación se detiene limpiamente.
        self.corriendo = False

        # Referencia a la ventana. Se crea en _construir_ventana().
        self.ventana = None

        # Ángulo actual de rotación (para la animación de "pensando").
        # Va de 0 a 360 grados y se reinicia.
        self.angulo = 0

        # Fase del pulso (para animaciones de "escuchando" y "hablando").
        # Usamos seno(fase) para crear un efecto suave de ida y vuelta.
        self.fase_pulso = 0.0

    # ============================================================
    # ARRANQUE Y PARADA
    # ============================================================

    def iniciar(self):
        """
        Arranca la interfaz en un hilo separado.

        ¿Por qué un hilo separado?
        Tkinter tiene su propio "loop" (mainloop) que bloquea el hilo
        donde corre. Si lo pusiéramos en el hilo principal, el loop
        de voz (escuchar → pensar → hablar) no podría funcionar.
        Con un hilo separado, ambos loops corren al mismo tiempo.
        """
        self.corriendo = True

        # daemon=True significa que este hilo muere automáticamente
        # cuando el programa principal termina. Sin esto, cerrar Eli
        # dejaría la ventana abierta como un proceso zombie.
        hilo = threading.Thread(target=self._ejecutar, daemon=True)
        hilo.start()

    def detener(self):
        """Cierra la interfaz limpiamente."""
        self.corriendo = False

    def _ejecutar(self):
        """
        Método interno que corre en el hilo separado.
        Construye la ventana, inicia la animación y arranca mainloop.
        """
        self._construir_ventana()
        self._animar()            # Inicia el ciclo de animación
        self.ventana.mainloop()   # Tkinter toma el control del hilo

    # ============================================================
    # CONSTRUCCIÓN DE LA VENTANA
    # ============================================================

    def _construir_ventana(self):
        """Crea todos los elementos visuales de la interfaz."""

        # --- Ventana principal ---
        self.ventana = tk.Tk()
        self.ventana.title("Eli — Asistente de Voz")
        self.ventana.configure(bg=NEGRO)
        self.ventana.geometry("520x680")
        self.ventana.resizable(False, False)

        # Protocolo para cuando el usuario cierra la ventana con la X.
        # Sin esto, cerrar la ventana no detendría el programa.
        self.ventana.protocol("WM_DELETE_WINDOW", self._al_cerrar)

        # --- Canvas: lienzo para dibujar el anillo ---
        # Canvas es el widget de tkinter para dibujo libre.
        # Aquí dibujamos el anillo animado, el nombre y las líneas.
        # highlightthickness=0 quita el borde blanco predeterminado.
        self.canvas = tk.Canvas(
            self.ventana,
            width=520, height=380,
            bg=NEGRO,
            highlightthickness=0
        )
        self.canvas.pack()

        # --- Líneas decorativas estilo HUD ---
        # Líneas horizontales finas que dan el look de interfaz tecnológica.
        self.canvas.create_line(
            20, 20, 500, 20,
            fill=AZUL_TENUE, width=1
        )
        self.canvas.create_line(
            20, 360, 500, 360,
            fill=AZUL_TENUE, width=1
        )

        # Pequeños marcadores en las esquinas (detalle estético).
        for x in [20, 500]:
            for y in [20, 360]:
                self.canvas.create_rectangle(
                    x - 3, y - 3, x + 3, y + 3,
                    fill=AZUL_ELECTRICO, outline=""
                )

        # --- Nombre "ELI" ---
        # El nombre grande en el centro superior del anillo.
        self.canvas.create_text(
            260, 100,
            text="E L I",
            font=("Consolas", 36, "bold"),
            fill=CYAN
        )

        # Subtítulo debajo del nombre.
        self.canvas.create_text(
            260, 135,
            text="VOICE ASSISTANT",
            font=("Consolas", 10),
            fill=AZUL_MEDIO
        )

        # --- Anillo: arcos que forman el círculo animado ---
        # Dibujamos 4 arcos (cuartos de círculo) para poder
        # animarlos individualmente (rotar, cambiar color, etc.).
        # create_arc dibuja un arco dentro de un rectángulo delimitador.
        # El rectángulo va de (x1,y1) a (x2,y2), y el arco se dibuja dentro.
        self.arcos = []
        centro_x, centro_y = 260, 240
        radio = 80

        for i in range(4):
            arco = self.canvas.create_arc(
                centro_x - radio, centro_y - radio,  # Esquina superior izq
                centro_x + radio, centro_y + radio,  # Esquina inferior der
                start=i * 90,      # Ángulo donde empieza (0°, 90°, 180°, 270°)
                extent=70,          # Cuántos grados abarca (70° de 90° posibles)
                outline=AZUL_TENUE, # Color del trazo
                width=3,            # Grosor del trazo
                style=tk.ARC        # Solo el arco, sin relleno
            )
            self.arcos.append(arco)

        # Arco interior más pequeño (detalle decorativo).
        self.arco_interno = self.canvas.create_arc(
            centro_x - 50, centro_y - 50,
            centro_x + 50, centro_y + 50,
            start=0, extent=360,
            outline=AZUL_TENUE,
            width=1,
            style=tk.ARC
        )

        # Punto central del anillo.
        self.punto_centro = self.canvas.create_oval(
            centro_x - 4, centro_y - 4,
            centro_x + 4, centro_y + 4,
            fill=AZUL_TENUE, outline=""
        )

        # --- Texto de estado ("Escuchando...", "Pensando...", etc.) ---
        self.texto_estado = self.canvas.create_text(
            260, 340,
            text="En espera",
            font=("Consolas", 11),
            fill=GRIS
        )

        # --- Panel inferior: log de conversación ---
        # Frame es un contenedor que agrupa widgets.
        frame_log = tk.Frame(self.ventana, bg=NEGRO)
        frame_log.pack(fill=tk.BOTH, expand=True, padx=15, pady=(5, 15))

        # Etiqueta del log.
        tk.Label(
            frame_log,
            text="─── CONVERSACIÓN ───",
            font=("Consolas", 9),
            fg=AZUL_MEDIO, bg=NEGRO
        ).pack()

        # Text widget: área de texto con scroll para el historial.
        # state=tk.DISABLED impide que el usuario escriba en él.
        # wrap=tk.WORD hace que las líneas largas salten por palabra.
        self.log = tk.Text(
            frame_log,
            bg="#050A10",          # Fondo casi negro
            fg=AZUL_ELECTRICO,
            font=("Consolas", 10),
            height=10,
            wrap=tk.WORD,
            state=tk.DISABLED,     # Solo lectura
            borderwidth=1,
            relief=tk.SOLID,
            highlightbackground=AZUL_TENUE,
            highlightthickness=1,
            padx=10, pady=8,
            insertbackground=CYAN  # Color del cursor (no visible, pero por si acaso)
        )
        self.log.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # Configuramos colores especiales para los tags del log.
        # Los tags permiten dar formato distinto a partes del texto.
        # "usuario" = lo que dijiste tú (cyan).
        # "eli" = lo que respondió Eli (azul eléctrico).
        # "sistema" = mensajes del sistema (gris).
        self.log.tag_configure("usuario", foreground=CYAN)
        self.log.tag_configure("eli", foreground=AZUL_ELECTRICO)
        self.log.tag_configure("sistema", foreground=GRIS)

    # ============================================================
    # MÉTODOS PÚBLICOS (los que usa main.py)
    # ============================================================

    def cambiar_estado(self, nuevo_estado):
        """
        Cambia el estado visual de Eli.

        Args:
            nuevo_estado: "espera", "escuchando", "pensando" o "hablando"
        """
        self.estado = nuevo_estado

        # Mapa de estados a textos que se muestran en la interfaz.
        textos = {
            "espera": "En espera",
            "escuchando": "🎤  Escuchando...",
            "pensando": "💭  Pensando...",
            "hablando": "🔊  Hablando..."
        }
        texto = textos.get(nuevo_estado, "")

        # Mapa de estados a colores del texto de estado.
        colores = {
            "espera": GRIS,
            "escuchando": AZUL_ELECTRICO,
            "pensando": CYAN,
            "hablando": CYAN
        }
        color = colores.get(nuevo_estado, GRIS)

        # _actualizar_seguro usa ventana.after() para hacer cambios
        # desde otro hilo sin crashear tkinter.
        self._actualizar_seguro(
            lambda: self.canvas.itemconfig(
                self.texto_estado, text=texto, fill=color
            )
        )

    def mostrar_usuario(self, texto):
        """Muestra en el log lo que dijo el usuario."""
        self._agregar_log(f"Tú: {texto}", "usuario")

    def mostrar_eli(self, texto):
        """Muestra en el log lo que respondió Eli."""
        self._agregar_log(f"Eli: {texto}", "eli")

    def mostrar_sistema(self, texto):
        """Muestra un mensaje del sistema en el log."""
        self._agregar_log(f"[{texto}]", "sistema")

    # ============================================================
    # ANIMACIÓN DEL ANILLO
    # ============================================================

    def _animar(self):
        """
        Bucle de animación. Se llama a sí mismo cada 50ms.

        ventana.after(ms, función) es el "setTimeout" de tkinter.
        Programa una función para ejecutarse después de X milisegundos.
        Esto crea un bucle suave sin bloquear la interfaz.
        """
        if not self.corriendo:
            self.ventana.destroy()
            return

        # Según el estado actual, ejecutamos una animación diferente.
        if self.estado == "escuchando":
            self._animar_pulso(velocidad=0.08, color_fuerte=AZUL_ELECTRICO)

        elif self.estado == "pensando":
            self._animar_giro()

        elif self.estado == "hablando":
            self._animar_pulso(velocidad=0.15, color_fuerte=CYAN)

        else:  # "espera"
            self._animar_reposo()

        # Programar la siguiente iteración en 50ms (~20 FPS).
        self.ventana.after(50, self._animar)

    def _animar_pulso(self, velocidad, color_fuerte):
        """
        Hace que el anillo pulse (se ilumine y apague suavemente).

        velocidad: qué tan rápido pulsa (más alto = más rápido).
        color_fuerte: color en el pico del pulso.

        Usamos math.sin() para crear un movimiento suave de ida y vuelta.
        sin() va de -1 a 1. Nosotros lo convertimos a 0-1 para usarlo
        como "intensidad" del color.
        """
        self.fase_pulso += velocidad

        # sin() retorna -1 a 1. Sumamos 1 y dividimos entre 2 → 0 a 1.
        # Esto nos da un número entre 0 (apagado) y 1 (máximo brillo).
        intensidad = (math.sin(self.fase_pulso) + 1) / 2

        # Interpolamos entre el color tenue y el color fuerte.
        color = self._interpolar_color(AZUL_TENUE, color_fuerte, intensidad)

        # Aplicamos el color a todos los arcos del anillo.
        for arco in self.arcos:
            self.canvas.itemconfig(arco, outline=color, width=3)

        # El punto central y el arco interno también pulsan.
        self.canvas.itemconfig(self.arco_interno, outline=color)
        self.canvas.itemconfig(self.punto_centro, fill=color)

    def _animar_giro(self):
        """
        Hace que los arcos del anillo roten.

        Incrementamos el ángulo y actualizamos la posición de cada arco.
        Los 4 arcos están separados 90° entre sí, creando el efecto de
        un anillo girando.
        """
        self.angulo = (self.angulo + 5) % 360  # +5° por frame, reinicia en 360

        for i, arco in enumerate(self.arcos):
            # Cada arco empieza 90° después del anterior, más la rotación.
            inicio = self.angulo + (i * 90)
            self.canvas.itemconfig(
                arco,
                start=inicio,
                outline=CYAN,
                width=3
            )

        # El punto central brilla fijo durante el pensamiento.
        self.canvas.itemconfig(self.arco_interno, outline=AZUL_MEDIO)
        self.canvas.itemconfig(self.punto_centro, fill=CYAN)

    def _animar_reposo(self):
        """
        Estado de reposo: anillo tenue y quieto.
        Reinicia las posiciones de los arcos a su estado original.
        """
        for i, arco in enumerate(self.arcos):
            self.canvas.itemconfig(
                arco,
                start=i * 90,        # Posición original
                outline=AZUL_TENUE,
                width=2              # Más delgado en reposo
            )

        self.canvas.itemconfig(self.arco_interno, outline=AZUL_TENUE)
        self.canvas.itemconfig(self.punto_centro, fill=AZUL_TENUE)

        # Reiniciamos la fase del pulso para que la próxima animación
        # empiece desde cero, no desde donde se quedó.
        self.fase_pulso = 0.0

    # ============================================================
    # UTILIDADES INTERNAS
    # ============================================================

    def _interpolar_color(self, color_a, color_b, factor):
        """
        Mezcla dos colores hexadecimales según un factor (0.0 a 1.0).

        factor=0.0 → color_a puro
        factor=1.0 → color_b puro
        factor=0.5 → mezcla 50/50

        Ejemplo: interpolar("#000000", "#00FFFF", 0.5) → "#007F7F"
        """
        # Convertir hex "#RRGGBB" a valores numéricos R, G, B.
        # [1:] quita el "#". int(x, 16) convierte hexadecimal a decimal.
        r1, g1, b1 = int(color_a[1:3], 16), int(color_a[3:5], 16), int(color_a[5:7], 16)
        r2, g2, b2 = int(color_b[1:3], 16), int(color_b[3:5], 16), int(color_b[5:7], 16)

        # Mezclar cada componente proporcionalmente.
        r = int(r1 + (r2 - r1) * factor)
        g = int(g1 + (g2 - g1) * factor)
        b = int(b1 + (b2 - b1) * factor)

        # Convertir de vuelta a hexadecimal. :02x = 2 dígitos hex con cero al inicio.
        return f"#{r:02x}{g:02x}{b:02x}"

    def _agregar_log(self, texto, tag):
        """
        Agrega una línea al log de conversación.

        Tkinter no permite modificar un Text que está en estado DISABLED.
        Por eso lo habilitamos momentáneamente, escribimos, y lo volvemos
        a deshabilitar.

        ventana.after() se usa porque este método puede ser llamado
        desde el hilo principal (main.py), pero tkinter solo permite
        cambios desde su propio hilo.
        """
        def _insertar():
            self.log.config(state=tk.NORMAL)     # Habilitar escritura
            self.log.insert(tk.END, texto + "\n", tag)  # Agregar texto con formato
            self.log.see(tk.END)                  # Auto-scroll al final
            self.log.config(state=tk.DISABLED)    # Volver a solo lectura

        self._actualizar_seguro(_insertar)

    def _actualizar_seguro(self, funcion):
        if self.ventana and self.corriendo:
            try:
                self.ventana.after(0, funcion)
            except Exception:
                pass

    def _al_cerrar(self):
        """Se ejecuta cuando el usuario cierra la ventana con la X."""
        self.corriendo = False
        self.ventana.destroy()


# --- Prueba directa ---
# Simula los estados de Eli para ver las animaciones.
if __name__ == "__main__":
    gui = InterfazEli()
    gui.iniciar()

    # Esperamos a que la ventana se construya.
    time.sleep(1)

    # Simulación de una conversación.
    estados = [
        ("escuchando", 3, None, None),
        (None, 0, "usuario", "Qué hora es"),
        ("pensando", 2, None, None),
        ("hablando", 3, "eli", "Son las 3 de la tarde."),
        ("espera", 3, "sistema", "Listo para siguiente comando"),
        ("escuchando", 3, None, None),
        (None, 0, "usuario", "Abre Chrome"),
        ("pensando", 1, None, None),
        ("hablando", 2, "eli", "Abriendo Chrome."),
        ("espera", 5, None, None),
    ]

    for estado, duracion, tipo_msg, msg in estados:
        if estado:
            gui.cambiar_estado(estado)
        if tipo_msg == "usuario":
            gui.mostrar_usuario(msg)
        elif tipo_msg == "eli":
            gui.mostrar_eli(msg)
        elif tipo_msg == "sistema":
            gui.mostrar_sistema(msg)
        time.sleep(duracion)

    gui.detener()
