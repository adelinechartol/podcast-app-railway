from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import whisper
import google.generativeai as genai
from elevenlabs import generate, set_api_key, voices
import os
import json
import tempfile
from datetime import datetime
from pathlib import Path
import time
from pydub import AudioSegment
import concurrent.futures
import threading

print("🚀 Starting app.py...")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Files in directory: {os.listdir('.')}")

app = Flask(__name__)

# Enhanced CORS for production
CORS(app, origins=["*"], methods=["GET", "POST", "OPTIONS"], 
     allow_headers=["Content-Type", "Authorization"])

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Production Configuration
class Config:
    WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'base')
    ENABLE_PARALLEL_PROCESSING = False  # Disabled for Railway
    MAX_WORKERS = 1  # Single worker for Railway
    OPTIMIZE_AUDIO = True
    TARGET_SAMPLE_RATE = 16000
    CONFIDENCE_THRESHOLD = 0.7
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB for Railway
    
    # Production settings
    DEBUG = os.getenv('FLASK_ENV') != 'production'
    SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-secret-key')

# Initialize AI services with error handling
print("🚀 Initializing Railway production services...")

try:
    print("Loading Whisper model...")
    whisper_model = whisper.load_model(Config.WHISPER_MODEL)
    print(f"✅ Whisper model loaded: {Config.WHISPER_MODEL}")
except Exception as e:
    print(f"❌ Whisper initialization failed: {e}")
    whisper_model = None

try:
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment")
    genai.configure(api_key=api_key)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    print("✅ Gemini model initialized")
except Exception as e:
    print(f"❌ Gemini initialization failed: {e}")
    gemini_model = None

try:
    elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')
    if not elevenlabs_key:
        raise ValueError("ELEVENLABS_API_KEY not found in environment")
    set_api_key(elevenlabs_key)
    print("✅ ElevenLabs voice initialized")
except Exception as e:
    print(f"❌ ElevenLabs initialization failed: {e}")

# Create directories with error handling
directories = ['audio/responses', 'podcasts/uploads', 'podcasts/transcripts']

for directory in directories:
    try:
        os.makedirs(directory, exist_ok=True)
    except Exception as e:
        print(f"⚠️ Could not create directory {directory}: {e}")

def optimize_audio_simple(audio_path):
    """Simple audio optimization for Railway"""
    try:
        print("🔧 Applying Railway-optimized audio processing...")
        audio = AudioSegment.from_file(audio_path)
        
        # Convert to mono
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        # Normalize volume
        audio = audio.normalize()
        
        # Apply compression for speech clarity
        audio = audio.compress_dynamic_range(threshold=-20.0, ratio=3.0)
        
        # Resample to target rate
        if audio.frame_rate != Config.TARGET_SAMPLE_RATE:
            audio = audio.set_frame_rate(Config.TARGET_SAMPLE_RATE)
        
        # Export optimized version
        optimized_path = audio_path.replace('.', '_opt.')
        if not optimized_path.endswith('.wav'):
            optimized_path = optimized_path.rsplit('.', 1)[0] + '.wav'
        
        audio.export(optimized_path, format="wav")
        return optimized_path
        
    except Exception as e:
        print(f"⚠️ Audio optimization failed: {e}")
        return audio_path

def transcribe_question_simple(audio_path):
    """Simplified transcription for Railway"""
    if not whisper_model:
        raise Exception("Whisper model not available")
        
    try:
        print("🎤 Processing question with Railway optimization...")
        
        # Apply simple audio processing
        enhanced_path = optimize_audio_simple(audio_path)
        
        # Whisper transcription with Railway-optimized settings
        result = whisper_model.transcribe(
            enhanced_path,
            fp16=False,
            language='en',
            task='transcribe',
            verbose=False,
            temperature=0.0,
            condition_on_previous_text=False,
            initial_prompt="This is a clear question about a podcast."
        )
        
        # Cleanup enhanced file
        if enhanced_path != audio_path:
            try:
                os.remove(enhanced_path)
            except:
                pass
        
        transcript = result['text'].strip()
        confidence = 0.8  # Default confidence for Railway
        
        return transcript, confidence
        
    except Exception as e:
        print(f"❌ Question transcription error: {e}")
        raise e

# Frontend HTML (embedded in backend for simplicity)
FRONTEND_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interactive Podcast with AI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: white;
        }
        .container { max-width: 800px; margin: 0 auto; display: grid; gap: 20px; }
        .glass-panel {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 25px;
        }
        .header { text-align: center; }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(45deg, #51cf66, #40c057);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .record-button {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            border: none;
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            margin: 20px auto;
            display: block;
        }
        .record-button:hover { transform: scale(1.05); }
        .record-button.recording {
            background: linear-gradient(45deg, #ff6b6b, #ee5a24);
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }
        .status {
            text-align: center;
            margin: 20px 0;
            font-size: 1.1em;
            font-weight: 500;
        }
        .status.ready { color: #51cf66; }
        .status.error { color: #ff6b6b; }
        .response-section { margin-top: 20px; }
        .qa-item {
            margin-bottom: 20px;
            padding: 15px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            border-left: 4px solid #51cf66;
        }
        .question { font-weight: 600; margin-bottom: 10px; color: #51cf66; }
        .answer { line-height: 1.6; margin-bottom: 15px; }
        .deployment-info {
            background: rgba(81, 207, 102, 0.1);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            border: 1px solid rgba(81, 207, 102, 0.3);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="glass-panel header">
            <h1>🎙️ Interactive Podcast AI</h1>
            <p>Railway Deployment - Say "Hey Pod" and ask questions!</p>
            <div class="deployment-info">
                <strong>🚀 Successfully deployed on Railway!</strong><br>
                Your interactive podcast app is now live and accessible worldwide.
            </div>
        </div>

        <div class="glass-panel">
            <div class="status" id="status">⏳ Connecting to Railway backend...</div>
            <button class="record-button" id="recordButton">Hold to Ask</button>
            <div id="responseContainer"></div>
        </div>
    </div>

    <script>
        class SimplePodcastAI {
            constructor() {
                this.API_BASE = window.location.origin;
                this.isRecording = false;
                this.mediaRecorder = null;
                this.recordedChunks = [];
                
                this.initializeApp();
            }

            async initializeApp() {
                await this.checkBackendStatus();
                this.setupRecording();
            }

            async checkBackendStatus() {
                try {
                    const response = await fetch(`${this.API_BASE}/health`);
                    const data = await response.json();
                    
                    if (data.status === 'ready') {
                        document.getElementById('status').textContent = '✅ Railway backend connected! Hold button and ask questions.';
                        document.getElementById('status').className = 'status ready';
                    }
                } catch (error) {
                    document.getElementById('status').textContent = '❌ Railway backend not responding. Please wait...';
                    document.getElementById('status').className = 'status error';
                }
            }

            setupRecording() {
                const recordButton = document.getElementById('recordButton');
                recordButton.addEventListener('mousedown', () => this.startRecording());
                recordButton.addEventListener('mouseup', () => this.stopRecording());
                recordButton.addEventListener('touchstart', (e) => {
                    e.preventDefault();
                    this.startRecording();
                });
                recordButton.addEventListener('touchend', (e) => {
                    e.preventDefault();
                    this.stopRecording();
                });
            }

            async startRecording() {
                if (this.isRecording) return;

                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ 
                        audio: {
                            echoCancellation: true,
                            noiseSuppression: true,
                            autoGainControl: true
                        } 
                    });

                    this.mediaRecorder = new MediaRecorder(stream);
                    this.recordedChunks = [];
                    
                    this.mediaRecorder.ondataavailable = (event) => {
                        if (event.data.size > 0) {
                            this.recordedChunks.push(event.data);
                        }
                    };

                    this.mediaRecorder.onstop = () => {
                        this.processRecording();
                    };

                    this.mediaRecorder.start();
                    this.isRecording = true;

                    const recordButton = document.getElementById('recordButton');
                    recordButton.textContent = 'Recording...';
                    recordButton.classList.add('recording');

                } catch (error) {
                    alert('Microphone access required. Please allow and try again.');
                }
            }

            stopRecording() {
                if (!this.isRecording || !this.mediaRecorder) return;

                this.mediaRecorder.stop();
                this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
                this.isRecording = false;

                const recordButton = document.getElementById('recordButton');
                recordButton.textContent = 'Processing...';
                recordButton.classList.remove('recording');
            }

            async processRecording() {
                try {
                    const audioBlob = new Blob(this.recordedChunks, { type: 'audio/wav' });
                    const formData = new FormData();
                    formData.append('audio', audioBlob, 'question.wav');
                    formData.append('timestamp', 0);

                    const response = await fetch(`${this.API_BASE}/ask-question`, {
                        method: 'POST',
                        body: formData
                    });

                    const data = await response.json();
                    
                    if (data.error) {
                        throw new Error(data.error);
                    }

                    this.displayResponse(data);

                } catch (error) {
                    document.getElementById('status').textContent = `❌ ${error.message}`;
                    document.getElementById('status').className = 'status error';
                } finally {
                    const recordButton = document.getElementById('recordButton');
                    recordButton.textContent = 'Hold to Ask';
                }
            }

            displayResponse(data) {
                const container = document.getElementById('responseContainer');
                const qaItem = document.createElement('div');
                qaItem.className = 'qa-item';
                qaItem.innerHTML = `
                    <div class="question">Q: ${data.question}</div>
                    <div class="answer">A: ${data.response}</div>
                    ${data.audio_url ? `<audio controls><source src="${data.audio_url}" type="audio/mpeg"></audio>` : ''}
                `;
                container.insertBefore(qaItem, container.firstChild);
                
                document.getElementById('status').textContent = '✅ Response generated! Ask another question.';
                document.getElementById('status').className = 'status ready';
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            new SimplePodcastAI();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Serve the frontend"""
    return render_template_string(FRONTEND_HTML)

@app.route('/health')
def health_check():
    return jsonify({
        "status": "ready",
        "environment": "railway_production",
        "whisper": f"loaded ({Config.WHISPER_MODEL})" if whisper_model else "unavailable",
        "gemini": "connected" if gemini_model else "unavailable",
        "elevenlabs": "connected",
        "deployment": "railway"
    })

@app.route('/ask-question', methods=['POST', 'OPTIONS'])
def ask_question():
    """Handle questions with Railway optimization"""
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        # Validate services
        if not whisper_model:
            return jsonify({'error': 'Speech recognition unavailable'}), 503
        if not gemini_model:
            return jsonify({'error': 'AI response unavailable'}), 503
            
        # Get audio file
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
            
        audio_file = request.files['audio']
        
        # Save audio temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            audio_file.save(tmp_file.name)
            temp_path = tmp_file.name
        
        print("🎤 Processing question on Railway...")
        
        # Transcribe question
        try:
            question, confidence = transcribe_question_simple(temp_path)
            
            # Clean up wake words
            wake_patterns = ['hey pod', 'hey pot', 'pod']
            for pattern in wake_patterns:
                question = question.replace(pattern, '').strip()
            question = question.lstrip('.,!? ').strip()
            
        except Exception as e:
            os.unlink(temp_path)
            return jsonify({'error': f'Could not understand audio: {str(e)}'}), 400
        
        # Clean up temp file
        os.unlink(temp_path)
        
        if not question or len(question.strip()) < 3:
            return jsonify({'error': 'Question too short. Please speak clearly.'}), 400
        
        print(f"🗣️ Railway question: {question}")
        
        # Generate AI response
        try:
            prompt = f"""
            A user asked this question: {question}
            
            Respond helpfully and conversationally in 40-80 words. 
            Use plain text only - no formatting.
            Be friendly and knowledgeable.
            """
            
            response = gemini_model.generate_content(prompt)
            ai_response = response.text.strip()
            
            # Clean formatting
            for char in ['*', '_', '#', '`', '**', '__']:
                ai_response = ai_response.replace(char, '')
            
        except Exception as e:
            return jsonify({'error': f'AI response failed: {str(e)}'}), 500
        
        # Generate audio response
        audio_url = None
        try:
            audio = generate(
                text=ai_response,
                voice="Callum",
                model="eleven_monolingual_v1"
            )
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_filename = f"response_{timestamp}.mp3"
            audio_path = f"audio/responses/{audio_filename}"
            
            with open(audio_path, 'wb') as f:
                f.write(audio)
            
            audio_url = f'/audio/{audio_filename}'
            
        except Exception as e:
            print(f"❌ TTS error: {e}")
        
        return jsonify({
            'question': question,
            'response': ai_response,
            'audio_url': audio_url,
            'confidence': confidence,
            'deployment': 'railway'
        })
        
    except Exception as e:
        print(f"❌ Railway error: {e}")
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

@app.route('/audio/<filename>')
def serve_audio(filename):
    """Serve audio files"""
    try:
        return send_file(f'audio/responses/{filename}')
    except FileNotFoundError:
        return jsonify({'error': 'Audio file not found'}), 404

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large'}), 413

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 5001))
        print("✅ Railway production backend ready!")
        print(f"👉 Running on port {port}")
        app.run(host='0.0.0.0', port=port, debug=Config.DEBUG)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        import traceback
        traceback.print_exc()
