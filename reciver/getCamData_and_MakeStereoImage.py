import serial
import cv2
import numpy as np
import torch
from torchvision.transforms import Compose, ToTensor, Resize

# ---------------------------------------------------------------------
# for Stereo Image

# MiDaSモデルのロード
def load_midas_model():
    print("Loading MiDaS model...")
    model = torch.hub.load("intel-isl/MiDaS", "MiDaS_small")
    model.eval()
    transform = Compose([ToTensor()])
    return model, transform

midas_model, midas_transform = load_midas_model()

# 入力画像をMiDaSに適したサイズに変換する
def prepare_image(img):
    target_size = (256, 256)  # MiDaS推奨サイズ
    resized_img = cv2.resize(img, target_size, interpolation=cv2.INTER_AREA)
    input_tensor = midas_transform(resized_img).unsqueeze(0)
    return input_tensor, resized_img

# 視差画像の生成
def create_disparity_images(img, depth_map):
    h, w = depth_map.shape
    left_image = img.copy()
    right_image = img.copy()

    # 深度に基づいて左右にシフト
    for y in range(h):
        for x in range(w):
            shift = int(depth_map[y, x] * 10)  # 深度に基づくシフト量を計算
            if x + shift < w:
                right_image[y, x] = img[y, x + shift]
            if x - shift >= 0:
                left_image[y, x] = img[y, x - shift]

    # 左右画像を結合 (SBS形式)
    sbs_image = np.concatenate((left_image, right_image), axis=1)
    return sbs_image

# JPEGデータから視差画像を作成
def create_disparity_images_handler(img):
    # 入力画像を準備
    input_tensor, resized_img = prepare_image(img)

    # # 深度推定
    # with torch.no_grad():
    #     depth_map = midas_model(input_tensor).squeeze().numpy()

    # # 深度マップのサイズを元画像サイズにリサイズ
    # depth_map_resized = cv2.resize(depth_map, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)

    # # 視差画像生成
    # disparity_image = create_disparity_images(img, depth_map_resized)

    disparity_image = None

    return disparity_image

# ---------------------------------------------------------------------
# for Serial Communication

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

# ---------------------------------------------------------------------
# for mian

WINDOW_NAME = 'Disparity Camera Image'
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

                    # 画像をリサイズ
                    input_tensor, resized_image = prepare_image(image)

                    # 深度推定
                    with torch.no_grad():
                        depth_map = midas_model(input_tensor).squeeze().numpy()

                    # 深度マップのサイズを元画像サイズにリサイズ
                    depth_map_resized = cv2.resize(depth_map, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_LINEAR)

                    # 視差画像生成
                    disparity_image = create_disparity_images(image, depth_map_resized)

                    # 5インチディスプレイの解像度に合わせてリサイズ
                    new_width = 1920
                    new_height = 1080

                    # 画像をリサイズ
                    resized_image = cv2.resize(disparity_image, (new_width, new_height))

                    # リサイズした画像を表示
                    cv2.imshow(WINDOW_NAME, resized_image)
                    
                    # プレビュー用の画像を表示
                    preview_image = cv2.resize(image, (640, 480))
                    cv2.imshow('Camera Preview', preview_image)

                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                else:
                    print(f"cv2.imdecode returned None. Buffer length: {len(jpg_buffer)}. Saving to file for inspection.")
                    # デバッグ用に先頭と末尾の数バイトを16進数で表示
                    print(f"Buffer head: {jpg_buffer.tobytes()[:20].hex()}")
                    print(f"Buffer tail: {jpg_buffer.tobytes()[-20:].hex()}")
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
