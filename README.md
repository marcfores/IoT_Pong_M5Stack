# IoT Remote Pong: ESP32 M5Stack & IMU Control

A distributed, real-time multiplayer implementation of the classic Pong game built for M5Stack-FIRE (ESP32) devices.

Developed for the *Interaction, Sensors, and Transducers* course, this project demonstrates hardware-to-hardware communication, sensor signal processing, and embedded systems programming using MicroPython.

## System Architecture & Features

*   **Master-Slave Network:** Centralized game logic on the master device to prevent state inconsistencies, with the slave acting as a remote terminal.
*   **Real-Time UDP Communication:** Low-latency data exchange via WiFi using UDP sockets and JSON payloads. Implements sequence numbering to discard out-of-order packets.
*   **IMU Sensor Control:** Paddle movement is driven by physical device tilt (pitch) measured via the integrated accelerometer and gyroscope.
*   **Signal Processing:** Applies real-time low-pass filtering and dead-zone calibration to smooth sensor readings and eliminate unintentional jitter.

## Repository Structure
*   `/src`: Contains the MicroPython scripts (`.py`) for both the Master and Slave devices.
*   `/docs`: Includes the full technical report (`.pdf`) detailing the physics algorithms, networking protocol, and system architecture.
