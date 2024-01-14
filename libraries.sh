sudo apt update
sudo apt install python3-pyaudio flac python3-espeak espeak python3-dotenv portaudio19-dev
# sudo apt install libportaudio0 
sudo apt install libportaudio2 libportaudiocpp0 portaudio19-dev libasound2-plugins --yes 

arecord -l
# **** List of CAPTURE Hardware Devices ****
# card 3: Device [USB PnP Sound Device], device 0: USB Audio [USB Audio]
#   Subdevices: 1/1
#   Subdevice #0: subdevice #0

aplay -l
# **** List of PLAYBACK Hardware Devices ****
# card 0: Headphones [bcm2835 Headphones], device 0: bcm2835 Headphones [bcm2835 Headphones]
#   Subdevices: 8/8
# card 4: UACDemoV10 [UACDemoV1.0], device 0: USB Audio [USB Audio]
#   Subdevices: 1/1
#   Subdevice #0: subdevice #0

sudo apt install ffmpeg
# to reproduce gtts mp3 output

sudo apt-get install sox libsox-fmt-all
# to reproduce gtts mp3 output FAST