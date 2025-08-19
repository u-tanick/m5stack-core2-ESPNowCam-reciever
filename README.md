# m5stack-core2-ESPNowCam-reciever

## EN

This program receives camera image data transmitted from m5stack-atoms3r-send-jyrodata-espnow via ESP-NOW and sends it to a PC through serial communication.

The connection with the PC assumes USB Type-C (USB3.0).

Sample programs for displaying images on the PC based on serial data are stored in the receiver/ folder.

- getCamData.py
  - A program that displays monocular camera images directly on the PC
- getCamData_and_MakeStereoImage.py
  - A program that creates pseudo stereo disparity images by calculating depth based on monocular images
  - Can be used for applications such as viewing the created stereo disparity images using smartphone VR cameras, etc.

## JA

このプログラムは  `m5stack-atoms3r-send-jyrodata-espnow` から送信されるカメラ画像データをESPNowで受信し、シリアル通信でPCに送るものです。

PCとの接続は、`USB Type-C（USB3.0）` を想定しています。

PC側でシリアルデータをもとに画像を表示するプログラムのサンプルを `reciver/` フォルダに格納しています。

- getCamData.py
  - 単眼のカメラ画像をそのままPC上に表示するプログラム
- getCamData_and_MakeStereoImage.py
  - 単眼画像をもとに、疑似的に深度を計算したステレオ視差画像を作成するプログラム
  - スマートフォン用のVRカメラなどを使用して、作成したステレオ視差画像を覗き見るなどの用途に使用できます。
