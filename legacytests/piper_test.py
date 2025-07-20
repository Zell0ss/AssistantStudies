
#%%
"""
following this instructions.
https://github.com/rhasspy/piper#running-in-python
"""
import subprocess
import pygame
import os
WAV_BATCH_FILE = "welcome.wav"
def text2wav(texto):
    if os.path.exists(WAV_BATCH_FILE):
        os.remove(WAV_BATCH_FILE)
    comando = f"echo '{texto}' | piper --model es_ES-carlfm-x_low --output_file {WAV_BATCH_FILE}"
    # Ejecutar el comando en un subproceso y esperar a que termine
    subprocess.run(comando, shell=True)
    # reproducir el wav resultante
    print("debug> playing sound")


def wav2pygame():
    # f = open(WAV_BATCH_FILE, 'rb')
    # data = f.read()
    # pygame.mixer.pre_init(channels=1, buffer=4096)
    # sound = pygame.mixer.Sound(buffer=data)
    # sound.play()
    my_sound=pygame.mixer.Sound(WAV_BATCH_FILE)
    my_sound.play()
    # pygame.quit()
#%%
import pyaudio
import wave

def reproducir_wav(chunk = 2048):
    

    f = wave.open("test.wav","rb")
    p = pyaudio.PyAudio()

    stream = p.open(format = p.get_format_from_width(f.getsampwidth()),
                    channels = f.getnchannels(),
                    rate = f.getframerate(),
                    output = True)

    data = f.readframes(chunk)

    while data:
        stream.write(data)
        data = f.readframes(chunk)

    stream.stop_stream()
    stream.close()

    p.terminate()

# %%
texto = "marineros embobados, miran al mar buscando una respuesta que no llega. "
#%%
text2wav(texto)
# %%
reproducir_wav(512)
# %%
os.system("aplay welcome.wav")
# %%

import gtts
gtts.lang.tts_langs()
myobj = gtts.gTTS(text = texto, lang="es", slow = False)
myobj.speed = 0.2
myobj.save("test.mp3")

# %%
os.system("play -q test.mp3 tempo 1.5")
# %%
os.system("ffplay -v 0 -nodisp -autoexit test.mp3")