#%%
"""
# Necesario para usar pydub -> FFmpeg library
sudo apt update
sudo apt install ffmpeg
ffmpeg -version

# whisper models 
tiny: Más rápido, menos preciso
base: Equilibrio entre velocidad y precisión
small: Mejor precisión, más lento
medium: Muy buena precisión
large: Máxima precisión, más lento

"""
from pydub import AudioSegment
import dotenv
import os
import whisper
dotenv.load_dotenv()
WHISPER_MODEL = os.getenv("OPENAI_WHISPER_MODEL")

def audio_to_mp3(audio_file:str)->str:
    """
    Convert a .wav file to a .mp3 file.

    Args:
    audio_file: path to audio file

    Returns:
    path to the output .mp3 file
    """
    audio = AudioSegment.from_wav(audio_file)
    output_file = audio_file.replace(".wav", ".mp3")
    audio.export(output_file, format="mp3")
    return output_file

def audio_to_text(audio_file:str)->dict:
    """
    Extractas from .mp3 file its subtitles.
    for a 18 min/4MB MP3 -> 7 minutes
    audio_file: path to audio file
    in result["text"] is the transcript in plain text

    Args: dictionary with the subtitles

    Returns:
    path to the output .mp3 file
    """
    model = whisper.load_model(WHISPER_MODEL)
    result = model.transcribe(audio_file)
    result["filename"] = audio_file
    return result

def generate_srt(transcript)->str:
    """
    Genera un archivo de subtítulos en formato .srt a partir de la transcripción.

    Args:
    transcript: diccionario con la transcripción que se obtiene al llamar a
    audio_to_text().

    Devuelve:
    path al archivo de subtítulos generado.
    """
    output_file = transcript["filename"].replace(".mp3", ".srt")
    with open(output_file, "w", encoding="utf-8") as f:
        for i, segmento in enumerate(transcript["segments"]):
            # Formato SRT: número de subtítulo
            f.write(f"{i + 1}\n")
            
            # Formato de tiempo SRT (HH:MM:SS,mmm --> HH:MM:SS,mmm)
            inicio = format_time(segmento["start"])
            fin = format_time(segmento["end"])
            f.write(f"{inicio} --> {fin}\n")
            
            # Texto del subtítulo
            f.write(f"{segmento['text'].strip()}\n\n")
    return output_file

def format_time(segundos):
    """
    Convierte una cantidad de segundos en una cadena de tiempo formateada en el estilo SRT para marcar posicion de subtítlulo.

    Args:
    segundos: Tiempo en segundos que se desea convertir.

    Devuelve:
    Una cadena en formato "HH:MM:SS,mmm" donde HH son horas, MM son minutos, SS son segundos,
    y mmm son milisegundos.
    """

    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    secs = int(segundos % 60)
    milisecs = int((segundos - int(segundos)) * 1000)
    return f"{horas:02d}:{minutos:02d}:{secs:02d},{milisecs:03d}"


"""
USAGE 

# first we transform wav to mp3 to try and go down from 30Mb to 5MB
audio_file = "GLP-1 Agonists_ Benefits, Risks, and Usage.wav"
audio_mp3 = audio_to_mp3(audio_file)

# then the transcript (7 min)
transcript = audio_to_text(audio_mp3)
print(transcript["text"])

# and finally the SRT
srt_file = generate_srt(transcript)
print(srt_file)

"""