# 📸 Autonomous Instagram Uploader Bot (2026 Ready)

An advanced, autonomous engine designed to manage, moderate, and upload content to **Instagram Reels/Posts** via Telegram. Powered by **Playwright**, this system utilizes persistent browser contexts to mimic human behavior and maintain active sessions, effectively bypassing modern bot detection.

---

## 🛠️ The Hybrid Workflow

Unlike standard automation, this script implements a **dual-thread asynchronous system** for maximum efficiency and account safety:

1.  **Instant Moderation:** As soon as a video is sent to the bot, it is forwarded to the Admin for immediate approval/rejection.
2.  **Smart Upload Queue:** Approved videos enter a "waiting list" that is processed automatically every **15-20 minutes**, ensuring a consistent content flow while avoiding spam flags.

---

## 🔥 Key Features

* **🛡️ Live Admin Moderation:** Interactive Telegram buttons to approve or discard content in real-time.
* **⭐ Premium Access:** Use the `/prem <password>` command in the video caption to skip moderation and publish in just 60 seconds.
* **⏱️ Dynamic Scheduler:** Randomized intervals (15-20 min) between posts to keep the account "organic" for Meta's algorithms.
* **🔍 Robust Login Verification:** The bot checks for an active session on startup. If the session expires, it pauses and gives you 5 minutes to log in manually.
* **♻️ Auto-Recovery:** Scans local directories on startup to resume pending tasks after a reboot or crash.
* **🎭 Anti-Detection Engine:** Uses persistent Chrome profiles and forced DOM interaction (`force=True`) to handle Instagram's complex UI.

---

## 📋 Prerequisites

* **Python 3.10+**
* **Google Chrome** installed on the host machine.
* **Telegram Bot Token** (Obtained from [@BotFather](https://t.me/botfather)).
* **Your Telegram ID** (Obtained from [@userinfobot](https://t.me/userinfobot)).

---

## ⚙️ Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/GeckCore/Instagram_Bot.git](https://github.com/GeckCore/Instagram_Bot.git)
    cd Instagram_Bot
    ```

2.  **Install Python dependencies:**
    ```bash
    pip install pyTelegramBotAPI playwright
    ```

3.  **Install Browser Engine (Playwright):**
    ```bash
    python -m playwright install chromium
    ```

4.  **Configuration:**
    Open `bot_instagram.py` and update the following variables:
    * `TOKEN_TELEGRAM`: Your Telegram Bot Token.
    * `ADMIN_CHAT_ID`: Your numerical Telegram ID for moderation.
    * `PASSWORD_SISTEMA`: Your secret password for `/prem` uploads.
    * `MODO_OCULTO`: Set to `False` for the first run.

5.  **First Run & Session Link:**
    Run the bot:
    ```bash
    python bot_instagram.py
    ```
    A browser window will open. **Log in to Instagram manually.** Accept cookies and select "Save Login Info". Once you reach the main feed, the bot will detect the session, save it in the `ig_perfil_bot` folder, and start working.

💡 **Pro Tip:** Once the session is linked, set `MODO_OCULTO = True` in the script to let the bot work in the background without opening visible windows.

---

## 📂 Project Structure

* `bot_instagram.py`: The main engine.
* `ig_perfil_bot/`: Directory where your Instagram session and cookies are stored.
* `cola_videos/`: Temporary folder for videos waiting for moderation or upload.
