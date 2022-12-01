import pr
from imageio.v2 import imread
import sys

def usage():
    print("img2ir - Transmits image to Dot Matrix ESL\n")
    print("Usage:")
    print("img2dm.py port image barcode page (x y)\n")
    print("  name: file name for generated .ir file")
    print("  image: image file (208x102 pixels)")
    print("  barcode: 17-character barcode data")
    print("  page: page number to update (0~15)")
    exit()

arg_count = len(sys.argv)
if arg_count < 4:
    usage()

def record_run(run_count):
    # Convert to binary
    del bits[:]
    while run_count:
        bits.insert(0, run_count & 1)
        run_count >>= 1
    # Zero length coding
    for b in bits[1:]:
        compressed.append(0)
    if len(bits):
        compressed.extend(bits)

# Open image file
image = imread(sys.argv[2])
width = image.shape[1]
height = image.shape[0]
if width > 208 or height > 112:
    print("Image should be 208*112 pixels or less.")
    exit()

# Get PLID from barcode string
PLID = pr.get_plid(sys.argv[3])

page = int(sys.argv[4])
if page < 0 or page > 15:
    print("Page can only be between 0 and 15.")
    exit()

bits = []
size_raw = width * height

# Convert image to 1-bit
pixels = []
for row in image:
    for rgb in row:
        pixels.append(int(round((0.21 * rgb[0] + 0.72 * rgb[1] + 0.07 * rgb[2]) / 255)))

print("Compressing %i pixels..." % size_raw)

# First pixel
compressed = []
run_pixel = pixels[0]
run_count = 1
compressed.append(run_pixel)
for pixel in pixels[1:]:
    if pixel == run_pixel:
        # Add to run
        run_count += 1
    else:
        # Record run
        record_run(run_count)
        run_count = 1
        run_pixel = pixel

# Record last run
if run_count > 1:
    record_run(run_count)

size_compressed = len(compressed)

# Decide on compression or not
if size_compressed < size_raw:
    print("Compression ratio: %.1f%%" % (100 - ((size_compressed * 100) / float(size_raw))))
    data = compressed
    compression_type = 2
else:
    print("Compression ratio suxx, using raw data")
    data = pixels
    compression_type = 0

# Pad data to multiple of bits_per_frame
bits_per_frame = 20 * 8
data_size = len(data)
padding = bits_per_frame - (data_size % bits_per_frame)
for b in range(0, padding):
    data.append(0)

padded_data_size = len(data)
frame_count = padded_data_size // bits_per_frame

frames = []

# Ping frame
frames.append(pr.make_ping_frame(PLID, 400))

print("Generating %i data frames..." % frame_count)

# Parameters frame
frame = pr.make_mcu_frame(PLID, 0x05)
pr.append_word(frame, data_size // 8)   # Byte count
frame.append(0x00)                      # Unused
frame.append(compression_type)
frame.append(page)
pr.append_word(frame, width)
pr.append_word(frame, height)
pr.append_word(frame, 0)
pr.append_word(frame, 0)
pr.append_word(frame, 0x0000)   # Keycode
frame.append(0x88)              # 0x80 = update, 0x08 = set base page
pr.append_word(frame, 0x0000)   # Enabled pages (bitmap)
frame.extend([0x00, 0x00, 0x00, 0x00])
pr.terminate_frame(frame, 1)
frames.append(frame)

# Data frames
i = 0
for fr in range(0, frame_count):
    frame = pr.make_mcu_frame(PLID, 0x20)
    pr.append_word(frame, fr)
    for by in range(0, 20):
        v = 0
        # Bit string to byte
        for bi in range(0, 8):
            v <<= 1
            v += data[i + bi]
        frame.append(v)
        i += 8
    pr.terminate_frame(frame, 1)
    frames.append(frame)

# Refresh frame
frames.append(pr.make_refresh_frame(PLID))

fileName = sys.argv[1]

#Output
with open(f"{fileName}.ir", "w") as f:
    f.write(f"""Filetype: IR Signals file
Version: 1
#
name: {fileName}
type: raw
frequency: 38000
duty_cycle: 0.330000
data: """)
    for fr in frames:
        for b in fr:
            f.write(str(b) + " ")
    f.close()
