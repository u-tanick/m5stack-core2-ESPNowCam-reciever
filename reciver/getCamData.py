import serial
import cv2
import numpy as np

# シリアルポートの設定
COM_PORT = 'COM10'
BAUD_RATE = 460800

# JPEGデータの境界
JPEG_START = b'\xff\xd8'  # JPEGヘッダー (開始)
JPEG_END = b'\xff\xd9'    # JPEGフッター (終了)

def read_image_from_serial(ser):
    buffer = bytearray()
    timeout_counter = 0  # タイムアウト用カウンタ
    MAX_TIMEOUT = 100  # タイムアウト制限回数

    while True:
        # 1回分のデータを読み取る
        data = ser.read(4096) # 読み込みサイズを増やす
        if data:
            buffer.extend(data)
            timeout_counter = 0  # データを受信した場合、タイムアウトカウンタをリセット
        else:
            timeout_counter += 1
            if timeout_counter > MAX_TIMEOUT:
                raise TimeoutError("Timed out waiting for image data.")

        # バッファ内でJPEG開始と終了を探す
        # JPEG_STARTが見つかるまでデータを読み飛ばす
        while True:
            start_idx = buffer.find(JPEG_START)
            if start_idx == -1:
                data = ser.read(4096) # 読み込みサイズを増やす
                if not data:
                    timeout_counter += 1
                    if timeout_counter > MAX_TIMEOUT:
                        raise TimeoutError("Timed out waiting for JPEG_START.")
                    continue
                buffer.extend(data)
                timeout_counter = 0
            else:
                # JPEG_STARTが見つかったら、それ以前のデータを破棄
                if start_idx > 0:
                    buffer = buffer[start_idx:]
                    start_idx = 0 # 新しいバッファでの開始位置は0

                end_idx = buffer.find(JPEG_END, start_idx + len(JPEG_START))
                if end_idx != -1:
                    # JPEGデータを抽出
                    jpg_data = buffer[start_idx:end_idx + len(JPEG_END)]
                    print(f"Found JPEG: start_idx={start_idx}, end_idx={end_idx}, length={len(jpg_data)}")
                    buffer = buffer[end_idx + len(JPEG_END):]  # 残りをバッファに保存
                    return np.frombuffer(jpg_data, dtype=np.uint8)
                else:
                    # JPEG_ENDが見つからない場合、さらにデータを読み込む
                    print(f"Found JPEG_START at {start_idx}, but no JPEG_END yet. Current buffer size: {len(buffer)}")
                    data = ser.read(4096) # 読み込みサイズを増やす
                    if not data:
                        timeout_counter += 1
                        if timeout_counter > MAX_TIMEOUT:
                            raise TimeoutError("Timed out waiting for JPEG_END.")
                        continue
                    buffer.extend(data)
                    timeout_counter = 0
        return None # Should not reach here

def main():
    with serial.Serial(COM_PORT, BAUD_RATE, timeout=2) as ser:
        print(f"Connected to {COM_PORT} at {BAUD_RATE} baud.")
        frame_count = 0
        while True:
            try:
                jpg_buffer = read_image_from_serial(ser)
                if jpg_buffer is None:
                    print("No complete JPEG buffer received yet. Continuing...")
                    continue

                image = cv2.imdecode(jpg_buffer, cv2.IMREAD_COLOR)
                if image is not None:
                    frame_count += 1
                    print(f"Successfully decoded frame {frame_count}. Image shape: {image.shape}")
                    resized = cv2.resize(image, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                    # resized = cv2.resize(image, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_LINEAR)
                    cv2.imshow('Camera Image', resized)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                else:
                    print(f"cv2.imdecode returned None. Buffer length: {len(jpg_buffer)}. Saving to file for inspection.")
                    # デバッグ用に先頭と末尾の数バイトを16進数で表示
                    print(f"Buffer head: {jpg_buffer.tobytes()[:20].hex()}") # .tobytes() を追加
                    print(f"Buffer tail: {jpg_buffer.tobytes()[-20:].hex()}") # .tobytes() を追加
                    with open(f"received_frame_error_{frame_count}.jpg", "wb") as f:
                        f.write(jpg_buffer.tobytes())
                    frame_count += 1 # Increment even on error to save unique files
            except TimeoutError as e:
                print(f"Timeout: {e}. Retrying...")
                continue
            except Exception as e:
                print(f"Error: {e}")
                break

        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
