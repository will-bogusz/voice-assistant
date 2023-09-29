import os
import tkinter as tk
from tkinter import Canvas
import pyaudio
import wave
from datetime import datetime
from pydub import AudioSegment
from elevenlabs import generate,  stream, set_api_key
import threading
import openai
import time

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Active Listener AI")

        self.mp3_file_path = ""
        
        self.first_recording = True
        self.is_recording = False
        self.is_audio_ready = False

        # grey button with red square to denote record
        self.record_btn_canvas = Canvas(root, width=200, height=200, bg='white')
        self.record_btn_canvas.pack(side='left')
        self.record_btn_canvas.create_rectangle(10, 10, 190, 190, fill='gray', outline='gray')
        self.record_btn_canvas.create_oval(70, 70, 130, 130, fill='red', outline='red')
        self.record_btn_canvas.bind("<Button-1>", self.toggle_recording)
        
        # # green play arrow greyed out
        self.playback_btn_canvas = Canvas(root, width=200, height=200, bg='white')
        self.playback_btn_canvas.pack(side='right')
        self.playback_btn_canvas.create_rectangle(10, 10, 190, 190, fill='lightgray', outline='lightgray')
        self.playback_btn_canvas.create_polygon(80, 50, 80, 150, 150, 100, fill='darkgray', outline='darkgray')
        
        self.playback_btn_canvas.bind("<Button-1>", self.craft_response)

    def save_temp_audio(self, prefix, parent, ending):
        timestamp_str = time.strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"{prefix}-{timestamp_str}.{ending}"
        file_path = os.path.join(parent, file_name)

        return file_path

    def toggle_recording(self, event):
        if self.is_recording:
            self.is_recording = False
        else:
            self.start_recording()

    def start_recording(self):
        self.is_recording = True

        if (self.first_recording):
            timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.folder_name = f"Conversation-{timestamp_str}"
            os.makedirs(self.folder_name, exist_ok=True)
            self.first_recording = False
        
        # red square appears when recording starts
        self.record_btn_canvas.create_rectangle(10, 10, 190, 190, fill='red', outline='red')
        print("Start recording")
        
        # recording thread
        threading.Thread(target=self.record).start()

    def record(self):
        p = pyaudio.PyAudio()
        
        # open audio interface
        stream = p.open(format=pyaudio.paInt16,
                                  channels=1,
                                  rate=44100,
                                  input=True,
                                  frames_per_buffer=1024)
        frames = []

        while self.is_recording:
            data = stream.read(1024)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        p.terminate()

        self.record_btn_canvas.create_rectangle(10, 10, 190, 190, fill='gray', outline='gray')
        self.record_btn_canvas.create_oval(70, 70, 130, 130, fill='red', outline='red')
        print("Stop recording")

        wav_file_path = self.save_temp_audio("audio", self.folder_name, "wav")

        with wave.open(wav_file_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(44100)
            wf.writeframes(b''.join(frames))

        
        # wav to mp3
        self.mp3_file_path = os.path.splitext(wav_file_path)[0] + '.mp3'
        AudioSegment.from_wav(wav_file_path).export(self.mp3_file_path, format='mp3')

        os.remove(wav_file_path)
        
        # enable playback button
        self.playback_btn_canvas.create_rectangle(10, 10, 190, 190, fill='gray', outline='gray')
        self.playback_btn_canvas.create_polygon(80, 50, 80, 150, 150, 100, fill='green', outline='green')
        self.is_audio_ready = True

    def send_to_whisper(self, audio_file_path):
        openai.api_base = "https://api.openai.com/v1"
        openai.api_key_path = "openai.txt"

        try:
            audio_file= open(audio_file_path, "rb")
            transcript = openai.Audio.translate("whisper-1", audio_file)
            return transcript['text']
        except FileNotFoundError:
            raise Exception(f"Audio file not found: {audio_file_path}")
        except Exception as e:
            raise Exception(f"Error transcribing audio: {str(e)}")
        

    def send_to_gpt(self, transcription):
        openai.api_base = "https://openrouter.ai/api/v1"
        openai.api_key_path = "openrouter.txt"

        response = openai.ChatCompletion.create(
          #model = "",
          model="openai/gpt-3.5-turbo",
          messages=[
                {"role": "system", "content": "You are a helpful virtual assistant. Limit your responses to be as concise as possible unless the user specifically requests otherwise."},
                {"role": "user", "content": transcription}
            ],
          headers={
            "HTTP-Referer": "http://bogusz.co",
          },
          stream=True,
        )

        for chunk in response:
            part = chunk['choices'][0]['delta']
            if len(part) != 0:
                text = part['content']
                text = text.replace('\n', '. ')
                yield text
            else:
                return ""

        

    def text_to_speech(self, transcript):
        with open('eleven.txt', 'r') as file:
        api_key = file.read().strip()
    
        set_api_key(api_key)
        
        
        audio_stream = generate(
            text=self.send_to_gpt(transcript),
            voice="Antoni",
            model="eleven_monolingual_v1",
            stream=True
        )
        
        stream(audio_stream)

    def craft_response(self, _):
        transcription = self.send_to_whisper(self.mp3_file_path)
        print("Transcription: " + transcription)
        self.text_to_speech(transcription)




if __name__ == '__main__':
    root = tk.Tk()
    app = App(root)
    root.mainloop()
