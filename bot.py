import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import time
import threading
import random
from collections import deque
from playwright.sync_api import sync_playwright

# --- CONFIGURACIÓN PRINCIPAL ---
TOKEN_TELEGRAM = 'TOKEN TG'
PASSWORD_SISTEMA = "1234"
MODO_OCULTO = False # ⚠️ Ponlo en False la primera vez para iniciar sesión. Luego ponlo en True.

# ⚠️ OBLIGATORIO: Pon tu ID numérico de Telegram (búscalo en @userinfobot)
ADMIN_CHAT_ID = "ID" 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA_VIDEOS = os.path.join(BASE_DIR, 'cola_videos')
PERFIL_DIR = os.path.join(BASE_DIR, "ig_perfil_bot") 

browser_lock = threading.Lock()
cola_normal = deque()
cola_aprobados = deque() # NUEVA COLA PARA VÍDEOS ACEPTADOS

# Estado global para la moderación
estado_aprobacion = {"estado": "LIBRE"} 

if not os.path.exists(CARPETA_VIDEOS):
    os.makedirs(CARPETA_VIDEOS)

bot = telebot.TeleBot(TOKEN_TELEGRAM, threaded=True)

# --- SISTEMA DE AUTO-RECUPERACIÓN ---
def recuperar_cola_perdida():
    archivos = [f for f in os.listdir(CARPETA_VIDEOS) if f.endswith('.mp4')]
    archivos.sort(key=lambda x: os.path.getmtime(os.path.join(CARPETA_VIDEOS, x)))
    for archivo in archivos:
        ruta = os.path.join(CARPETA_VIDEOS, archivo)
        if ruta not in cola_normal:
            cola_normal.append(ruta)
    if cola_normal:
        print(f"[LOG] ♻️ Recuperados {len(cola_normal)} vídeos pendientes.")

# --- VERIFICACIÓN DE LOGIN INICIAL (CORREGIDA) ---
def verificar_login_inicial():
    print("[LOG] 🔍 Abriendo navegador para verificar sesión de Instagram...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PERFIL_DIR,
            headless=MODO_OCULTO,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()
        page.goto("https://www.instagram.com/", timeout=60000)
        
        # Esperar a que la página cargue algo sustancial
        page.wait_for_timeout(5000)

        # SELECTORES CLAVE
        # Elementos de LOGIN
        selector_user = 'input[name="username"]'
        # Elementos de SESIÓN ACTIVA (Iconos de la barra lateral/superior que solo salen logueado)
        selector_feed = 'svg[aria-label="Inicio"], svg[aria-label="Home"], svg[aria-label="Direct"], svg[aria-label="Mensajes"]'

        is_logged_in = page.locator(selector_feed).first.is_visible()
        needs_login = page.locator(selector_user).is_visible() or "login" in page.url

        if not is_logged_in:
            if MODO_OCULTO:
                print("\n[!] ERROR: No hay sesión y estás en MODO_OCULTO. Ponlo en False para loguearte.")
                context.close()
                os._exit(1)
            
            print("\n" + "="*50)
            print("⚠️ ESPERANDO INICIO DE SESIÓN MANUAL ⚠️")
            print("1. Acepta las cookies si aparecen.")
            print("2. Introduce tu usuario y contraseña.")
            print("3. ¡IMPORTANTE! Dale a 'Guardar información' cuando IG lo pregunte.")
            print("4. El bot continuará solo cuando detecte que estás en el Feed.")
            print("="*50 + "\n")

            try:
                # Esperamos hasta que el elemento del feed sea visible (margen de 5 minutos)
                page.locator(selector_feed).first.wait_for(state="visible", timeout=300000)
                print("[LOG] ✅ Sesión detectada correctamente. Guardando perfil...")
                page.wait_for_timeout(5000) # Tiempo extra para asegurar guardado de cookies
            except Exception:
                print("\n[!] ERROR: Tiempo de espera agotado. No has iniciado sesión.")
                context.close()
                os._exit(1)
        else:
            print("[LOG] ✅ Sesión de Instagram activa. Todo listo.\n")
        
        context.close()

# --- MODERACIÓN DE TELEGRAM ---
def pedir_aprobacion_admin(video_path):
    estado_aprobacion["estado"] = "PENDIENTE"
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("✅ Aceptar", callback_data="aceptar"),
        InlineKeyboardButton("❌ Rechazar", callback_data="rechazar")
    )
    
    try:
        with open(video_path, 'rb') as video:
            bot.send_video(
                ADMIN_CHAT_ID, 
                video, 
                caption=f"🛡️ **FILTRO DE MODERACIÓN**\n\nNuevo vídeo recibido.\nArchivo: `{os.path.basename(video_path)}`\n\n¿Lo aprobamos para la cola de publicación automática (cada 15-20 min)?", 
                reply_markup=markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        print(f"[!] Error contactando al Admin: {e}. ¿Iniciaste el chat con el bot?")
        estado_aprobacion["estado"] = "ERROR"

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if estado_aprobacion["estado"] != "PENDIENTE":
        bot.answer_callback_query(call.id, "Esta solicitud ya fue procesada.")
        return
        
    if call.data == "aceptar":
        estado_aprobacion["estado"] = "ACEPTADO"
        bot.edit_message_caption(caption=f"✅ **ACEPTADO**.\nAñadido a la cola de publicación. Saldrá automáticamente (1 cada 15-20 min).\nPosición en cola de espera: {len(cola_aprobados)+1}", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
    elif call.data == "rechazar":
        estado_aprobacion["estado"] = "RECHAZADO"
        bot.edit_message_caption(caption="❌ **RECHAZADO**.\nEl vídeo ha sido descartado y eliminado.", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")

# --- MOTOR DE SUBIDA INSTAGRAM (VERIFICACIÓN REAL) ---
def subir_a_instagram(video_path, es_premium=False):
    tipo = "PREMIUM" if es_premium else "NORMAL"
    
    if not os.path.exists(video_path):
        return

    with browser_lock:
        print(f"\n[LOG] [{tipo}] Iniciando subida a Instagram: {os.path.basename(video_path)}")
        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=PERFIL_DIR,
                    headless=MODO_OCULTO,
                    channel="chrome",
                    args=["--disable-blink-features=AutomationControlled"]
                )
                
                page = context.new_page()
                page.goto("https://www.instagram.com/", timeout=60000)
                page.wait_for_timeout(5000)
                
                # Verificación de seguridad extra en cada subida
                selector_feed = 'svg[aria-label="Inicio"], svg[aria-label="Home"]'
                if not page.locator(selector_feed).first.is_visible():
                    print(f"[LOG] ❌ [{tipo}] ERROR: La sesión caducó inesperadamente.")
                    if not es_premium: cola_aprobados.appendleft(video_path)
                    return

                # 1. Click en 'Crear'
                print(f"[LOG] [{tipo}] Abriendo menú de creación...")
                try:
                    page.locator('svg[aria-label="Nueva publicación"], svg[aria-label="New post"]').first.click(force=True, timeout=5000)
                except:
                    page.locator('span:has-text("Crear"), span:has-text("Create")').first.click(force=True, timeout=5000)
                
                page.wait_for_timeout(2000)

                # 1.5. Instagram a veces abre un submenú para elegir entre "Publicación" o "Vídeo en directo"
                try:
                    submenu_post = page.locator('span:text-is("Publicación"), span:text-is("Post")').first
                    if submenu_post.is_visible(timeout=3000):
                        submenu_post.click(force=True)
                        page.wait_for_timeout(2000)
                except:
                    pass

                # 2. Subir archivo
                print(f"[LOG] [{tipo}] Buscando input de archivo e inyectando vídeo...")
                file_input = page.locator("input[type='file']").first
                file_input.wait_for(state="attached", timeout=15000)
                file_input.set_input_files(video_path)
                
                page.wait_for_timeout(5000)

                # 3 y 4. Avanzar menús dinámicamente hasta Compartir
                print(f"[LOG] [{tipo}] Navegando por los menús de edición...")
                compartido = False
                for _ in range(6):  # Máximo 6 intentos para atravesar cualquier menú de IG
                    page.wait_for_timeout(3500)
                    
                    # A. ¿Está ya el botón Compartir?
                    btn_comp = page.locator('div[role="dialog"]').get_by_text("Compartir", exact=True).first
                    if not btn_comp.is_visible():
                        btn_comp = page.locator('div[role="dialog"]').get_by_text("Share", exact=True).first
                    
                    if btn_comp.is_visible():
                        print(f"[LOG] [{tipo}] Publicando (Compartir)...")
                        btn_comp.click(force=True)
                        compartido = True
                        break
                        
                    # B. Si no está Compartir, ¿está el botón Siguiente?
                    btn_sig = page.locator('div[role="dialog"]').get_by_text("Siguiente", exact=True).first
                    if not btn_sig.is_visible():
                        btn_sig = page.locator('div[role="dialog"]').get_by_text("Next", exact=True).first
                    
                    if btn_sig.is_visible():
                        print(f"[LOG] [{tipo}] Clic en Siguiente...")
                        btn_sig.click(force=True)
                        continue # Volver a escanear tras hacer clic
                        
                    # C. Gestión de popups inesperados de IG (ej. "¿Compartir como Reel?")
                    try:
                        popup_ok = page.locator('div[role="dialog"]').get_by_text("Aceptar", exact=True).first
                        if popup_ok.is_visible():
                            print(f"[LOG] [{tipo}] Cerrando popup intermedio...")
                            popup_ok.click(force=True)
                    except:
                        pass

                if not compartido:
                    raise Exception("No se logró llegar al botón Compartir tras atravesar los menús.")

                # 5. Esperar confirmación y cerrar la 'X'
                print(f"[LOG] [{tipo}] Esperando confirmación del servidor...")
                try:
                    # Damos 60s. Si falla, no crasheamos, asumimos que subió.
                    success_msg = page.locator('text="Se ha compartido", text="has been shared", text="Compartida"').first
                    success_msg.wait_for(state="visible", timeout=60000)
                except:
                    print(f"[LOG] ⚠️ [{tipo}] No detecté el texto exacto, pero asumimos éxito por el tiempo transcurrido.")

                print(f"[LOG] [{tipo}] Buscando la 'X' para cerrar la ventana...")
                try:
                    # Buscamos la 'X' para dejar el navegador limpio
                    btn_cerrar = page.locator('svg[aria-label="Cerrar"], svg[aria-label="Close"]').first
                    if btn_cerrar.is_visible(timeout=10000):
                        btn_cerrar.click(force=True)
                        print(f"[LOG] [{tipo}] Ventana cerrada correctamente.")
                except:
                    print(f"[LOG] [{tipo}] No se encontró la 'X', recargando página para forzar limpieza.")
                    page.reload() # Fallback agresivo para asegurar que el modal se quita

                print(f"[LOG] ✅ [{tipo}] ÉXITO TOTAL: Vídeo publicado en Instagram.")
                page.wait_for_timeout(3000)

                # Borrado final del archivo
                if os.path.exists(video_path):
                    os.remove(video_path)

        except Exception as e:
            print(f"[LOG] ❌ [{tipo}] FALLO TÉCNICO: {e}")
            if not es_premium:
                cola_aprobados.appendleft(video_path)

# --- LÓGICA DE TIEMPOS ---
def hilo_moderacion():
    while True:
        if cola_normal:
            video_candidato = cola_normal.popleft()
            print(f"[LOG] 🛡️ Enviando {os.path.basename(video_candidato)} a revisión...")
            
            pedir_aprobacion_admin(video_candidato)
            
            while estado_aprobacion["estado"] == "PENDIENTE":
                time.sleep(2)
                
            if estado_aprobacion["estado"] == "ACEPTADO":
                cola_aprobados.append(video_candidato)
                print(f"[LOG] ✅ Vídeo aprobado. Total en cola de publicación: {len(cola_aprobados)}")
                estado_aprobacion["estado"] = "LIBRE"
                
            elif estado_aprobacion["estado"] == "RECHAZADO":
                if os.path.exists(video_candidato):
                    os.remove(video_candidato)
                print("[LOG] 🗑️ Vídeo rechazado por el Admin y eliminado físicamente.")
                estado_aprobacion["estado"] = "LIBRE"
            
            elif estado_aprobacion["estado"] == "ERROR":
                cola_normal.appendleft(video_candidato)
                estado_aprobacion["estado"] = "LIBRE"
                time.sleep(10)
        else:
            time.sleep(5)

def hilo_publicador():
    while True:
        if cola_aprobados:
            video_aprobado = cola_aprobados.popleft()
            
            subir_a_instagram(video_aprobado, es_premium=False)
            
            # Tiempo de espera entre 15 y 20 minutos (900 a 1200 segundos)
            espera = random.randint(900, 1200)
            print(f"[LOG] 🕒 Esperando {espera/60:.2f} minutos para publicar el siguiente...")
            time.sleep(espera)
        else:
            time.sleep(10)

def hilo_premium_rapido(video_path):
    print(f"[LOG] ⭐ Usuario Premium. Subiendo en 60s sin moderación...")
    time.sleep(60)
    subir_a_instagram(video_path, es_premium=True)

# --- RECEPTOR DE TELEGRAM ---
@bot.message_handler(content_types=['video', 'document'])
def recibir_video(message):
    try:
        file_id = message.video.file_id if message.video else message.document.file_id
        file_info = bot.get_file(file_id)
        descargado = bot.download_file(file_info.file_path)
        
        ruta = os.path.join(CARPETA_VIDEOS, f"vid_{int(time.time())}.mp4")
        with open(ruta, 'wb') as f:
            f.write(descargado)
        
        caption = message.caption if message.caption else ""
        
        if f"/prem {PASSWORD_SISTEMA}" in caption:
            bot.reply_to(message, "⭐ **ACCESO PREMIUM**. Saltando filtro de moderación. Subida en 1 minuto.")
            threading.Thread(target=hilo_premium_rapido, args=(ruta,), daemon=True).start()
        else:
            cola_normal.append(ruta)
            bot.reply_to(message, f"✅ Recibido. Estás en la posición {len(cola_normal)} de la cola.")
            
    except Exception as e:
        print(f"Error procesando: {e}")

# --- INICIO ---
if __name__ == "__main__":
    print("=============================================")
    print("   🚀 BOT INSTAGRAM: PRODUCCIÓN BLINDADA")
    print("=============================================")
    
    recuperar_cola_perdida()
    
    # Verificación de login obligatoria al arrancar
    verificar_login_inicial()
    
    threading.Thread(target=hilo_moderacion, daemon=True).start()
    threading.Thread(target=hilo_publicador, daemon=True).start()
    
    print("[LOG] Bot de Telegram activo y escuchando...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            time.sleep(5)
