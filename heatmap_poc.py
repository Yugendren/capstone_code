import serial
import matplotlib.pyplot as plt
import numpy as np

# --- CONFIGURATION ---
# This is the only line we had to change!
SERIAL_PORT = "COM3"  
BAUD_RATE = 115200
# ---------------------

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"Connected to {SERIAL_PORT}...")

except serial.SerialException as e:
    print(f"Error: Could not open port {SERIAL_PORT}.")
    print("Is the STM32 plugged in? Is CubeIDE closed?")
    exit()

# Set up the plot
plt.ion() # Turn on interactive mode
fig, ax = plt.subplots()
data = np.zeros((2, 2))

im = ax.imshow(data, cmap='jet', vmin=0, vmax=4095) 
cbar = fig.colorbar(im)
cbar.set_label('Pressure (0-4095)')

print("Starting visualization. Press Ctrl+C in this terminal to stop.")
print("Press on your 2x2 sensor...")

try:
    while True:
        line = ser.readline().decode('utf-8').strip()

        if line:
            try:
                parts = line.split(',')
                p00 = int(parts[0])
                p01 = int(parts[1])
                p10 = int(parts[2])
                p11 = int(parts[3])
                
                data = np.array([[p00, p01], 
                                 [p10, p11]])
                
                im.set_data(data)
                fig.canvas.draw()
                fig.canvas.flush_events()
                
            except (ValueError, IndexError):
                print(f"Skipping bad data: {line}")

except KeyboardInterrupt:
    print("Stopping visualization.")
    ser.close()