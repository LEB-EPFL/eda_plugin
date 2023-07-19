import time

import matplotlib.pyplot as plt
import numpy as np
from pycromanager import Core, Studio


def spiral_coordinates(index, center, direction):
    row, col = center
    # if index == 0:
    #     return row, col

    step = 0
    steps_taken = 0
    directions = {
        "clockwise": [(0, 1), (1, 0), (0, -1), (-1, 0)],
        "counterclockwise": [(0, 1), (-1, 0), (0, -1), (1, 0)]
    }
    direction_index = 0

    position = [(row, col)]

    while steps_taken < index:
        dr, dc = directions[direction][direction_index]
        for _ in range(step):
            row += dr
            col += dc
            steps_taken += 1
            position.append((row, col))

            if steps_taken == index:
                break

        direction_index = (direction_index + 1) % 4
        if direction_index % 2 == 0:
            step += 1

        

    return position

core = Core()
studio = Studio()
data = studio.data()
acq = studio.acquisitions()

x = core.get_x_position()
y = core.get_y_position()
im_size = 261
n_px = 2304
n_r = 5
stitch = np.zeros((n_px * n_r, n_px * n_r))

position = spiral_coordinates(24, (0,0), 'clockwise')

print(np.array(position)[:,0])

positions = [(pos[0] * im_size + x, pos[1] * im_size + y) for pos in position]

position = [(-pos[0], -pos[1]) for pos in position]
positions_px = [(((pos[0]) + abs(np.array(position)[:,0].min())) * n_px, ((pos[1]) + abs(np.array(position)[:,1].min())) * n_px,) for pos in position]

print(positions_px)




store = data.create_ram_datastore()
display = studio.displays().create_display(store)
studio.displays().manage(store)
cb = data.coords_builder()
print(positions)

for idx, i in enumerate(positions):
    print(idx)
    core.set_xy_position(i[0], i[1])
    #core.set_xy_position(positions[0][0], positions[0][1])
    img = acq.snap().get(0)
    img_stream = img.get_raw_pixels()

    img_py = np.array(img_stream).reshape((n_px, n_px))
    stitch[positions_px[idx][1]:positions_px[idx][1] + n_px, positions_px[idx][0]:positions_px[idx][0] + n_px] = img_py
    coords = cb.time(idx).build()
    img_c = img.copy_with(coords, img.get_metadata())
    store.put_image(img_c)
store.freeze()

core.set_xy_position(positions[0][0], positions[0][1])

plt.imshow(stitch, vmin=95, vmax=200)
plt.show()


# live = studio.get_snap_live_manager()
# live.snap(True)
# core.set_relative_xy_position(distance, distance)
# live.snap(True)
# core.set_relative_xy_position(-distance, -distance)
# live.snap(True)