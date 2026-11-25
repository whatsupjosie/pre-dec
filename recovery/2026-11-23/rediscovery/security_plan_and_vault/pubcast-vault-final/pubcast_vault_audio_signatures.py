"""
PubCast Vault Audio Signatures
==============================
Distinctive 2-3 second audio chimes for vault operations.

Vault Open: Ascending, confident, warm - like a broadcast going live
Vault Close: Descending, satisfied, secure - like a show wrapping

These can be:
1. Generated as WAV files (using wave module)
2. Generated as MP3 (using pydub)
3. Used in CLI (play on vault init, intake, verify)
4. Used in API (play on successful operations)
"""

import wave
import struct
import math
import os
from pathlib import Path
from typing import List, Tuple

# ─────────────────────────────────────────────────────────────
#  Audio Generation Utilities
# ─────────────────────────────────────────────────────────────

class AudioSignature:
    """Generate PubCast Vault audio signatures."""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
    
    def generate_sine_wave(
        self,
        frequency: float,
        duration: float,
        amplitude: float = 0.3
    ) -> List[int]:
        """Generate a sine wave at given frequency."""
        num_samples = int(self.sample_rate * duration)
        samples = []
        
        for i in range(num_samples):
            t = i / self.sample_rate
            # Sine wave: A * sin(2πft)
            value = amplitude * math.sin(2 * math.pi * frequency * t)
            # Convert to 16-bit PCM
            sample = int(value * 32767)
            samples.append(sample)
        
        return samples
    
    def apply_envelope(
        self,
        samples: List[int],
        attack_ms: float = 10,
        release_ms: float = 100
    ) -> List[int]:
        """Apply attack/release envelope to smooth edges."""
        attack_samples = int(self.sample_rate * attack_ms / 1000)
        release_samples = int(self.sample_rate * release_ms / 1000)
        
        result = []
        
        # Attack phase (fade in)
        for i in range(len(samples)):
            if i < attack_samples:
                # Linear fade in
                factor = i / attack_samples
                result.append(int(samples[i] * factor))
            elif i >= len(samples) - release_samples:
                # Linear fade out
                factor = (len(samples) - i) / release_samples
                result.append(int(samples[i] * factor))
            else:
                # Full volume
                result.append(samples[i])
        
        return result
    
    def mix_samples(self, *sample_lists: List[int]) -> List[int]:
        """Mix multiple sample lists together."""
        max_len = max(len(s) for s in sample_lists)
        
        mixed = []
        for i in range(max_len):
            value = 0
            for samples in sample_lists:
                if i < len(samples):
                    value += samples[i]
            
            # Prevent clipping
            value = max(-32768, min(32767, int(value / len(sample_lists))))
            mixed.append(value)
        
        return mixed
    
    def write_wav(self, samples: List[int], filename: str) -> bool:
        """Write samples to WAV file."""
        try:
            with wave.open(filename, 'wb') as wav_file:
                # 1 channel (mono), 2 bytes per sample (16-bit), sample rate
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.sample_rate)
                
                # Convert samples to bytes
                packed = b''.join(struct.pack('<h', s) for s in samples)
                wav_file.writeframes(packed)
            
            return True
        except Exception as e:
            print(f"Error writing WAV: {e}")
            return False
    
    # ─────────────────────────────────────────────────────────────
    #  VAULT OPEN - Ascending, confident, broadcast-like
    # ─────────────────────────────────────────────────────────────
    
    def create_vault_open(self) -> List[int]:
        """
        Vault Open Signature (2.5 seconds)
        
        Musical idea:
        - Starts with a low, rich broadcast tone
        - Rises confidently upward (major arpeggio)
        - Ends with a bright, welcoming high note
        - Feels like a show starting - energetic and warm
        
        Structure:
        0.0s: Low tone (100 Hz) - establishes presence
        0.3s: Mid tone (200 Hz) - rising action
        0.6s: High tone (400 Hz) - confident peak
        0.9s: Very high tone (600 Hz) - bright finale
        1.2s: Harmonic resonance (all together)
        2.5s: Fade out
        """
        
        # Individual notes
        low_tone = self.generate_sine_wave(100, 0.3, amplitude=0.25)      # Deep, rich
        mid_tone = self.generate_sine_wave(200, 0.3, amplitude=0.28)      # Rising
        high_tone = self.generate_sine_wave(400, 0.3, amplitude=0.30)     # Confident
        very_high = self.generate_sine_wave(600, 0.3, amplitude=0.25)     # Bright
        
        # Harmonic richness - play multiple frequencies together
        harmonic = self.mix_samples(
            self.generate_sine_wave(200, 0.8, amplitude=0.15),  # 200 Hz base
            self.generate_sine_wave(300, 0.8, amplitude=0.12),  # 300 Hz harmonic
            self.generate_sine_wave(400, 0.8, amplitude=0.10),  # 400 Hz harmonic
        )
        
        # Combine into sequence
        sequence = low_tone + mid_tone + high_tone + very_high + harmonic
        
        # Apply smooth envelope
        final = self.apply_envelope(sequence, attack_ms=15, release_ms=150)
        
        return final
    
    # ─────────────────────────────────────────────────────────────
    #  VAULT CLOSE - Descending, satisfied, secure
    # ─────────────────────────────────────────────────────────────
    
    def create_vault_close(self) -> List[int]:
        """
        Vault Close Signature (2.5 seconds)
        
        Musical idea:
        - Starts with bright, confident notes
        - Descends in a satisfying sweep
        - Ends with a deep, secure, locked-in tone
        - Feels like a show wrapping up - everything secured
        
        Structure:
        0.0s: High tone (500 Hz) - bright start
        0.4s: Mid-high tone (350 Hz) - descending
        0.8s: Mid tone (250 Hz) - continuing down
        1.2s: Low tone (150 Hz) - deep and secure
        1.6s: Very low tone (80 Hz) - locked and final
        2.5s: Fade out
        """
        
        # Descending melody
        high_start = self.generate_sine_wave(500, 0.4, amplitude=0.28)     # Bright
        mid_high = self.generate_sine_wave(350, 0.4, amplitude=0.28)       # Descending
        mid_tone = self.generate_sine_wave(250, 0.4, amplitude=0.30)       # Steady
        low_tone = self.generate_sine_wave(150, 0.4, amplitude=0.32)       # Deep
        very_low = self.generate_sine_wave(80, 0.4, amplitude=0.25)        # Very deep/locked
        
        # Final secure resonance - deep and solid
        secure_resonance = self.mix_samples(
            self.generate_sine_wave(80, 0.5, amplitude=0.20),   # 80 Hz base
            self.generate_sine_wave(120, 0.5, amplitude=0.15),  # 120 Hz harmonic
            self.generate_sine_wave(160, 0.5, amplitude=0.12),  # 160 Hz harmonic
        )
        
        # Combine into sequence
        sequence = high_start + mid_high + mid_tone + low_tone + very_low + secure_resonance
        
        # Apply smooth envelope (longer release for satisfaction)
        final = self.apply_envelope(sequence, attack_ms=20, release_ms=200)
        
        return final
    
    # ─────────────────────────────────────────────────────────────
    #  Bonus: SUCCESS CHIME - Quick positive confirmation
    # ─────────────────────────────────────────────────────────────
    
    def create_success_chime(self) -> List[int]:
        """
        Success Chime (1 second)
        
        Quick, positive confirmation sound.
        Like a cash register or notification ding.
        """
        
        # Quick ascending pair
        note1 = self.generate_sine_wave(400, 0.2, amplitude=0.35)
        note2 = self.generate_sine_wave(600, 0.3, amplitude=0.35)
        
        # Harmonic richness
        harmonic = self.mix_samples(
            self.generate_sine_wave(600, 0.3, amplitude=0.15),
            self.generate_sine_wave(800, 0.3, amplitude=0.12),
        )
        
        sequence = note1 + note2 + harmonic
        final = self.apply_envelope(sequence, attack_ms=5, release_ms=100)
        
        return final
    
    # ─────────────────────────────────────────────────────────────
    #  Bonus: ERROR ALERT - Caution/warning sound
    # ─────────────────────────────────────────────────────────────
    
    def create_error_alert(self) -> List[int]:
        """
        Error Alert (1.5 seconds)
        
        Descending alert - something needs attention but not critical.
        """
        
        # Descending pair with slight buzz
        high = self.generate_sine_wave(500, 0.3, amplitude=0.30)
        low = self.generate_sine_wave(350, 0.3, amplitude=0.30)
        repeat = self.generate_sine_wave(500, 0.3, amplitude=0.25)
        final_low = self.generate_sine_wave(200, 0.3, amplitude=0.32)
        
        sequence = high + low + repeat + final_low
        final = self.apply_envelope(sequence, attack_ms=10, release_ms=150)
        
        return final


# ─────────────────────────────────────────────────────────────
#  Generate & Save All Signatures
# ─────────────────────────────────────────────────────────────

def generate_all_signatures(output_dir: str = ".") -> dict:
    """Generate all audio signatures and save as WAV files."""
    
    Path(output_dir).mkdir(exist_ok=True)
    audio = AudioSignature()
    
    signatures = {
        "vault_open": {
            "description": "Vault Opening - Ascending, confident broadcast",
            "duration": "2.5s",
            "function": audio.create_vault_open
        },
        "vault_close": {
            "description": "Vault Closing - Descending, secured, locked",
            "duration": "2.5s",
            "function": audio.create_vault_close
        },
        "success": {
            "description": "Success Confirmation - Quick positive ding",
            "duration": "1.0s",
            "function": audio.create_success_chime
        },
        "error": {
            "description": "Error Alert - Caution/attention needed",
            "duration": "1.5s",
            "function": audio.create_error_alert
        }
    }
    
    results = {}
    
    for name, info in signatures.items():
        print(f"Generating {name}...", end=" ")
        
        samples = info["function"]()
        filename = f"{output_dir}/pubcast_vault_{name}.wav"
        
        if audio.write_wav(samples, filename):
            file_size = os.path.getsize(filename)
            print(f"✓ ({file_size} bytes, {info['duration']})")
            results[name] = {
                "file": filename,
                "size": file_size,
                "description": info["description"]
            }
        else:
            print("✗ FAILED")
    
    return results


# ─────────────────────────────────────────────────────────────
#  Integration with Vault CLI & API
# ─────────────────────────────────────────────────────────────

class VaultAudioPlayer:
    """Play vault audio signatures on operations."""
    
    def __init__(self, audio_dir: str = "."):
        self.audio_dir = audio_dir
        self.available = self._check_audio_available()
    
    def _check_audio_available(self) -> bool:
        """Check if we can play audio."""
        try:
            import subprocess
            # Check for common audio players
            for player in ["ffplay", "mpv", "aplay", "paplay", "afplay"]:
                result = subprocess.run(
                    ["which", player],
                    capture_output=True,
                    timeout=1
                )
                if result.returncode == 0:
                    return True
            return False
        except:
            return False
    
    def play_vault_open(self):
        """Play vault opening signature."""
        if self.available:
            self._play_sound("pubcast_vault_vault_open.wav")
    
    def play_vault_close(self):
        """Play vault closing signature."""
        if self.available:
            self._play_sound("pubcast_vault_vault_close.wav")
    
    def play_success(self):
        """Play success chime."""
        if self.available:
            self._play_sound("pubcast_vault_success.wav")
    
    def play_error(self):
        """Play error alert."""
        if self.available:
            self._play_sound("pubcast_vault_error.wav")
    
    def _play_sound(self, filename: str):
        """Play a sound file using available player."""
        import subprocess
        
        filepath = Path(self.audio_dir) / filename
        
        if not filepath.exists():
            return
        
        try:
            # Try different players in order
            for player in ["ffplay", "mpv", "aplay", "paplay", "afplay"]:
                try:
                    subprocess.run(
                        [player, "-nodisp", "-autoexit", str(filepath)],
                        capture_output=True,
                        timeout=5
                    )
                    return
                except FileNotFoundError:
                    continue
        except Exception as e:
            pass  # Silent fail - audio player not critical


# ─────────────────────────────────────────────────────────────
#  Example Usage
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("="*70)
    print("PubCast Vault Audio Signature Generator")
    print("="*70)
    print()
    
    # Generate all signatures
    results = generate_all_signatures("./pubcast_vault_audio")
    
    print()
    print("="*70)
    print("Generated Audio Signatures:")
    print("="*70)
    
    for name, info in results.items():
        print(f"\n✓ {name.upper()}")
        print(f"  Description: {info['description']}")
        print(f"  File: {info['file']}")
        print(f"  Size: {info['size']} bytes")
    
    print()
    print("="*70)
    print("Integration Examples:")
    print("="*70)
    print("""
# In pubcast_vault_cli.py:

player = VaultAudioPlayer("./pubcast_vault_audio")

# On vault initialization
vault.initialize(password)
player.play_vault_open()  # Cha-CHING!

# On successful file intake
file_id = vault.intake_file(path)
player.play_success()  # Ding!

# On vault close
vault.shutdown()
player.play_vault_close()  # Secure lock sound

# On corruption detected
if corruption:
    player.play_error()  # Alert sound
""")
    
    print()
    print("All audio files ready for integration!")


# ─────────────────────────────────────────────────────────────
#  AudioPlayer — Simple facade used by CLI (Session 4)
# ─────────────────────────────────────────────────────────────

class AudioPlayer:
    """
    Thin facade over VaultAudioPlayer for CLI integration.
    
    Usage:
        player = AudioPlayer(vault_dir)
        player.play("vault_open")
        player.play("success")
        player.play("error")
        player.play("vault_close")
    
    The wav files are expected in the same directory as the CLI script
    OR will be auto-generated on first use if missing.
    """
    
    SOUNDS = {
        "vault_open":  "pubcast_vault_vault_open.wav",
        "vault_close": "pubcast_vault_vault_close.wav",
        "success":     "pubcast_vault_success.wav",
        "error":       "pubcast_vault_error.wav",
    }
    
    def __init__(self, audio_dir: Path):
        self.audio_dir = Path(audio_dir)
        self._player = VaultAudioPlayer(str(audio_dir))
        self._ensure_wav_files()
    
    def _ensure_wav_files(self):
        """Generate wav files if they don't exist."""
        missing = [
            name for name in self.SOUNDS.values()
            if not (self.audio_dir / name).exists()
        ]
        if missing:
            try:
                generate_all_signatures(str(self.audio_dir))
            except Exception:
                pass  # Audio generation failure is non-fatal
    
    def play(self, sound: str):
        """Play a named sound. Fails silently if audio unavailable."""
        if not self._player.available:
            return
        method_map = {
            "vault_open":  self._player.play_vault_open,
            "vault_close": self._player.play_vault_close,
            "success":     self._player.play_success,
            "error":       self._player.play_error,
        }
        fn = method_map.get(sound)
        if fn:
            try:
                fn()
            except Exception:
                pass
