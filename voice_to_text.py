import speech_recognition as sr
r = sr.Recognizer()
wake_word="madre"
with sr.Microphone() as source:
    print(f"Listening for '{wake_word}'...")
    while True:
        audio = r.listen(source)
        try:
            print(">>speech detected")
            text = r.recognize_google(audio, language="es-ES")
            print(text)
            if wake_word in text.lower():
                print(">>Wake word detected.")
                break
        except sr.UnknownValueError:
            print(">>Unknown.")
            pass