import numpy as np
from torchvision import datasets, transforms
from PIL import Image

DIGITS = [0, 1, 2, 3, 4, 5]
IMG_SIZE = 8  # downsampled from 28x28

def _load_and_downsample(train=True, max_per_class=None):
    mnist = datasets.MNIST(root="./mnist_data", train=train, download=True)

    images = []
    labels = []
    class_counts = {d: 0 for d in DIGITS}

    for img, label in mnist:
        if label not in DIGITS:
            continue
        if max_per_class is not None and class_counts[label] >= max_per_class:
            continue

        img_small = img.resize((IMG_SIZE, IMG_SIZE), Image.LANCZOS)
        arr = np.asarray(img_small, dtype=np.float64) / 255.0  # normalize rgb to [0,1]
        images.append(arr.flatten())
        labels.append(DIGITS.index(label))  # remap to 0..5 for CrossEntropyLoss
        class_counts[label] += 1

    X = np.stack(images).astype(np.float64)
    y = np.array(labels, dtype=np.int64)
    return X, y

# We can raise this once we've confirmed sweep runtime at this size is doable
X, y = _load_and_downsample(train=True, max_per_class=200)

#for i in range(6):
    #print(f"\nImage {i + 1} | Label: {y[i]}")
    #print(", ".join(f"{pixel:.6f}" for pixel in X[i]))

print(f"Loaded {len(X)} samples, {IMG_SIZE}x{IMG_SIZE} = {IMG_SIZE*IMG_SIZE} features, "
      f"{len(DIGITS)} classes, {[np.sum(y==i) for i in range(len(DIGITS))]} per class")