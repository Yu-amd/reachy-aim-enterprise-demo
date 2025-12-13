# type: ignore
import shutil
from cv2_enumerate_cameras import enumerate_cameras, supported_backends
from cv2_enumerate_cameras.camera_info import CAP_ANY


try:
    from cv2.videoio_registry import getBackendName
except ModuleNotFoundError:
    def getBackendName(api):
        return {
            0: 'CAP_ANY',
            200: 'CAP_GSTREAMER',
            700: 'CAP_DSHOW',
            1200: 'CAP_AVFOUNDATION',
            1400: 'CAP_MSMF',
            1800: 'CAP_V4L2',
        }[api]


def print_table(titles, rows, title_aligns, column_aligns):
    terminal_size = shutil.get_terminal_size()
    column_count = len(titles)

    column_widths = [max(len(rows[j][i]) for j in range(len(rows))) for i in range(column_count)]
    column_widths = [max(len(titles[i]), column_widths[i]) for i in range(column_count)]

    reserved_width = sum(column_widths[:-1]) + column_count * 3 + 1

    column_widths[-1] = min(column_widths[-1], terminal_size.columns - reserved_width)

    def print_row(row, aligns):
        columns = []
        for i in range(column_count):
            w = column_widths[i]
            content = row[i]

            if len(content) > w:
                content = content[:w - 3] + '...'

            if aligns[i] == 'l':
                columns.append(content.ljust(w))
            elif aligns[i] == 'c':
                columns.append(content.center(w))
            elif aligns[i] == 'r':
                columns.append(content.rjust(w))
            else:
                raise ValueError('Invalid alignment value')
        print('| ' + ' | '.join(columns) + ' |')

    separator = '+' + '+'.join(['-' * (w + 2) for w in column_widths]) + '+'

    print(separator)
    print_row(titles, title_aligns)
    print(separator)
    for row in rows:
        print_row(row, column_aligns)
    print(separator)


def main():
    for backend in [CAP_ANY, *supported_backends]:
        backend_name = getBackendName(backend)
        print(f'{backend_name} backend:')
        camera_info_list = enumerate_cameras(backend)
        if not camera_info_list:
            print(f"No camera on {backend_name} backend.")
            continue

        print_table(
            titles=("index", "name", "vid", "pid", "path"),
            rows=[(
                str(camera_info.index),
                camera_info.name,
                " -- " if camera_info.vid is None else "{:04X}".format(camera_info.vid),
                " -- " if camera_info.pid is None else "{:04X}".format(camera_info.pid),
                "" if camera_info.path is None else camera_info.path,
            ) for camera_info in camera_info_list],
            title_aligns=('c', 'c', 'c', 'c', 'c'),
            column_aligns=('r', 'l', 'r', 'r', 'l'),
        )


if __name__ == '__main__':
    main()
