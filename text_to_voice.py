#%%
import pyttsx3

#%%
engine_eng = pyttsx3.init()
voice = engine_eng.getProperty('voices')[2]
print(voice)
engine_eng.setProperty('voice', voice.id)
engine_eng.say('Sally sells seashells by the seashore.')
engine_eng.say('The quick brown fox jumped over the lazy dog.')
engine_eng.runAndWait()

# %%
engine = pyttsx3.init()
voices = engine.getProperty('voices')
for voice in voices:
    print(voice, voice.id)
# %%
engine_sp = pyttsx3.init()
engine_sp.setProperty('voice', "spanish")
engine_sp.say('Tres tristes tigres comian trigo.')
engine_sp.say('Isaac Asimov es el mejor.')
engine_sp.say('Las tres leyes de la Robotica son: Ningun robot debera permitir que un ser humano sufra daño por accion o inaccion.')
engine_sp.runAndWait()
# %%
