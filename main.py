import asyncio
import math
import os
import subprocess
import warnings

import edge_tts
import whisper

# Wyłączamy nieistotne ostrzeżenia
warnings.filterwarnings("ignore")

# ==========================================
# 1. KONFIGURACJA ZMIENNYCH
# ==========================================


# Zmieniamy tekst na nazwę pliku, z którego skrypt ma czytać
PLIK_Z_TEKSTEM = "tekst.txt"

GLOS = "pl-PL-ZofiaNeural"  # lub "pl-PL-ZofiaNeural"

# Nazwy plików roboczych i końcowych
PLIK_AUDIO_PL = "lektor_pl.mp3"
WIDEO_ANGIELSKIE = "wideo_angielskie.mp4"  # Pamiętaj o zmianie na swoją nazwę!

WIDEO_LEKTOR_NAPISY = "1_wideo_lektor_napisy.mp4"
WIDEO_TYLKO_LEKTOR = "2_wideo_tylko_lektor.mp4"
WIDEO_TYLKO_NAPISY = "3_wideo_tylko_napisy.mp4"


# ==========================================
# 2. FUNKCJE POMOCNICZE
# ==========================================

def pobierz_czas_trwania(plik):
    """Używa systemowego ffprobe do zmierzenia długości pliku w sekundach"""
    komenda = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        plik
    ]
    wynik = subprocess.run(komenda, stdout=subprocess.PIPE, text=True, check=True)
    return float(wynik.stdout.strip())


def wczytaj_tekst_z_pliku(nazwa_pliku):
    print(f"\n[KROK 0/3] Wczytywanie tekstu z pliku {nazwa_pliku}...")
    if not os.path.exists(nazwa_pliku):
        print(f"-> [BŁĄD] Nie znaleziono pliku {nazwa_pliku}!")
        return None

    with open(nazwa_pliku, "r", encoding="utf-8") as plik:
        tekst = plik.read()

    # MAGICZNY WALEC: Usuwa wszelkie niepotrzebne taby, wielokrotne spacje i entery
    tekst = " ".join(tekst.split())

    if not tekst:
        print(f"-> [BŁĄD] Plik {nazwa_pliku} jest pusty!")
        return None

    print("-> Tekst wczytany i wyczyszczony z białych znaków.")
    return tekst


async def stworz_lektora(tekst):
    print(f"\n[KROK 1/3] Generowanie bazowego głosu lektora ({GLOS})...")
    # Generujemy głos w normalnym tempie (wersja próbna)
    communicate = edge_tts.Communicate(tekst, GLOS)
    await communicate.save(PLIK_AUDIO_PL)

    # Mierzymy długość wideo i wygenerowanego audio
    czas_wideo = pobierz_czas_trwania(WIDEO_ANGIELSKIE)
    czas_audio = pobierz_czas_trwania(PLIK_AUDIO_PL)

    print(f"-> Czas wideo: {czas_wideo:.2f} s")
    print(f"-> Czas audio: {czas_audio:.2f} s")

    # Jeśli lektor "wystaje" poza wideo, obliczamy i naprawiamy
    if czas_audio > czas_wideo:
        wspolczynnik = czas_audio / czas_wideo
        # math.ceil zaokrągla w górę, np. 12.1% -> 13% (daje margines bezpieczeństwa)
        procent = math.ceil((wspolczynnik - 1) * 100)

        print(f"-> [AKCJA] Audio za długie! Przyspieszam lektora automatycznie o +{procent}%...")

        nowy_rate = f"+{procent}%"
        communicate_szybki = edge_tts.Communicate(tekst, GLOS, rate=nowy_rate)
        await communicate_szybki.save(PLIK_AUDIO_PL)  # Nadpisujemy stary plik nowym
        print(f"-> Zapisano dopasowaną, przyspieszoną wersję: {PLIK_AUDIO_PL}")
    else:
        print("-> Audio mieści się w czasie wideo. Nie zmieniam tempa.")


def stworz_napisy():
    print("\n[KROK 2/3] Generowanie napisów SRT na podstawie głosu...")
    model = whisper.load_model("base")
    wynik = model.transcribe(PLIK_AUDIO_PL, language="pl")

    # Nasza własna, niezawodna funkcja do formatowania czasu dla napisów
    def format_czasu(sekundy):
        godziny = int(sekundy // 3600)
        minuty = int((sekundy % 3600) // 60)
        sek = sekundy % 60
        # Formatujemy na np. 00:00:03,500
        return f"{godziny:02d}:{minuty:02d}:{sek:06.3f}".replace(".", ",")

    print("-> Zapisywanie pliku SRT...")

    # Ręcznie tworzymy i zapisujemy plik SRT omijając błędy biblioteki
    with open("lektor_pl.srt", "w", encoding="utf-8") as plik_srt:
        # Whisper przechowuje każde zdanie w liście "segments"
        for i, segment in enumerate(wynik["segments"], start=1):
            start = format_czasu(segment["start"])
            koniec = format_czasu(segment["end"])
            tekst = segment["text"].strip()

            # Wpisujemy do pliku w formacie SRT
            plik_srt.write(f"{i}\n{start} --> {koniec}\n{tekst}\n\n")

    print("-> Zapisano: lektor_pl.srt")


def scalaj_wideo():
    print("\n[KROK 3/3] Renderowanie trzech wariantów wideo (FFmpeg)...")
    plik_srt = "lektor_pl.srt"

    if not os.path.exists(WIDEO_ANGIELSKIE):
        print(f"-> [BŁĄD] Nie znaleziono wideo: {WIDEO_ANGIELSKIE}")
        return

    # WARIANT 1: Lektor + Napisy (nasz dotychczasowy)
    print("-> Renderowanie Wariantu 1: Lektor + Napisy (to potrwa najdłużej)...")
    komenda_pelna = [
        "ffmpeg", "-y",
        "-i", WIDEO_ANGIELSKIE,
        "-i", PLIK_AUDIO_PL,
        "-map", "0:v:0",  # Obraz z oryginału
        "-map", "1:a:0",  # Dźwięk z polskiego lektora
        "-vf", f"fps=30,subtitles={plik_srt}",  # Usztywnienie fps i napisy
        "-c:v", "libx264",
        "-c:a", "aac",
        WIDEO_LEKTOR_NAPISY
    ]

    # WARIANT 2: Tylko Lektor, bez napisów
    print("-> Renderowanie Wariantu 2: Tylko Lektor (błyskawiczne!)...")
    komenda_tylko_lektor = [
        "ffmpeg", "-y",
        "-i", WIDEO_ANGIELSKIE,
        "-i", PLIK_AUDIO_PL,
        "-map", "0:v:0",  # Obraz z oryginału
        "-map", "1:a:0",  # Dźwięk z polskiego lektora
        "-c:v", "copy",  # KOPIUJEMY obraz 1:1, bez renderowania!
        "-c:a", "aac",
        WIDEO_TYLKO_LEKTOR
    ]

    # WARIANT 3: Tylko Napisy (oryginalny angielski dźwięk + polskie napisy)
    print("-> Renderowanie Wariantu 3: Tylko Napisy z oryginalnym audio...")
    komenda_tylko_napisy = [
        "ffmpeg", "-y",
        "-i", WIDEO_ANGIELSKIE,
        "-map", "0:v:0",  # Obraz z oryginału
        "-map", "0:a:0",  # Dźwięk z ORYGINAŁU (angielski)
        "-vf", f"fps=30,subtitles={plik_srt}",  # Napisy
        "-c:v", "libx264",
        "-c:a", "copy",  # Kopiujemy oryginalne audio bez utraty jakości
        WIDEO_TYLKO_NAPISY
    ]

    # Odpalenie wszystkich trzech komend po kolei
    try:
        subprocess.run(komenda_pelna, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"   [GOTOWE] {WIDEO_LEKTOR_NAPISY}")

        subprocess.run(komenda_tylko_lektor, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"   [GOTOWE] {WIDEO_TYLKO_LEKTOR}")

        subprocess.run(komenda_tylko_napisy, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"   [GOTOWE] {WIDEO_TYLKO_NAPISY}")

        print("\n[SUKCES] Wszystkie 3 warianty wideo zostały wygenerowane!")
    except subprocess.CalledProcessError as e:
        print(f"\n[BŁĄD FFmpeg] Coś poszło nie tak podczas łączenia plików: {e}")


# ==========================================
# 3. GŁÓWNY PROCES
# ==========================================

async def main():
    print("=== START AUTOMATYZACJI WIDEO ===")

    # Próbujemy wczytać tekst z pliku
    wczytany_tekst = wczytaj_tekst_z_pliku(PLIK_Z_TEKSTEM)

    # Jeśli plik nie istnieje lub jest pusty, przerywamy działanie
    if not wczytany_tekst:
        print("=== PROCES PRZERWANY ===")
        return

    # Jeśli tekst się wczytał, kontynuujemy magię
    await stworz_lektora(wczytany_tekst)
    stworz_napisy()
    scalaj_wideo()

    print("=== KONIEC ===")


# Uruchomienie
if __name__ == "__main__":
    asyncio.run(main())
