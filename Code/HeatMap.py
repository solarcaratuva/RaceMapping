from PIL import Image
import csv
import math
import sys
import utm
import random
import copy

class HeatMap:
    def __init__(
        self,
        filterMatrix,
        originalTrack,
        originalTrack_name: str,
        heatMap,
        dataType: str,
        bottom_range,
        top_range,
        output_file
    ):
        self.CSV_PATH = originalTrack
        self.filterMatrix = []
        self.originalTrack = originalTrack
        self.originalTrack_name = originalTrack_name
        self.output_file = output_file
        self.heatMap = heatMap
        self.dataType = dataType
        self.left_bound = 0
        self.top_bound = 0
        self.row_count = 0
        self.column_count = 0
        self.bottom_range = bottom_range
        self.top_range = top_range
        self.filterMatrix = self.filterMatrix
        self.width = 0
        self.height = 0
        
        self.CSV_to_MATRIX()
        self.create_matrix()

    # Creates a list of [0, 0] for all pixels.
    # Saves leftmost bound, topmost bound, row count, and column count.
    def create_matrix(self):
        CSV_CONVERTED_2D = []

        with open(self.CSV_PATH, "r") as f:
            data = csv.reader(f)

            for row in data:
                CSV_CONVERTED_2D.append([0, 0])

                if row[5:] == ['0', '1']:
                    self.row_count = int(row[0]) - 1

                if row[0] == '1':
                    self.left_bound = float(row[1])
                    self.top_bound = float(row[2])
                    print(self.left_bound)
                    print(self.top_bound)

        CSV_CONVERTED_2D.pop()  # Exclude header row
        self.column_count = len(CSV_CONVERTED_2D) // self.row_count

        return CSV_CONVERTED_2D

    def create_filter(self, twod_array):
        new_array = copy.deepcopy(twod_array)

        for y in range(0, len(new_array)):
            for x in range(0, len(new_array[0])):
                new_array[y][x] = self.spread(new_array, y, x)
        return new_array

    # Deprecated function: converts CSV to Matrix for parsing.
    def CSV_to_MATRIX(self):
        print("Deprecated function: CSV_TO_MATRIX")
        with open(self.CSV_PATH, "r", newline="") as f:
            rows = [row for row in csv.reader(f) if row]
        max_col = 0
        max_row = 0
        if not rows:
            return []
        
        for row in rows:
            try:
                if type(int(row[0])) != type("str"):

                    max_col = max(int(row[5]), max_col)
                    max_row = max(int(row[6]), max_row)
            except Exception as e:
                print(e)
        matrix = [
            [None for _ in range(max_col + 1)]
            for _ in range(max_row + 1)
        ]

        for row in rows:
            try:
                if type(int(row[0])) != type("str"):
                    x = float(row[1])
                    y = float(row[2])
                    col = int(row[5])
                    r = int(row[6])
                    matrix[r][col] = (x, y)
            except Exception as e:
                pass
        self.filterMatrix = matrix
        return matrix

    # Given coordinates in bounds, locate row and column numbers.
    def coordinate_finder(self, lat, lon):
        utm_lat_lon = utm.from_latlon(lat, lon)
        easting, northing = utm_lat_lon[0], utm_lat_lon[1]
        
        row_location = -(northing - self.top_bound) / 3
        column_location = (easting - self.left_bound) / 3
        row_location = int(row_location // 1)
        column_location = int(column_location // 1)

        location = (int(row_location), int(column_location))

        return location

    def matrix_test(
        self,
        output_path="perimeter.png",
        size_percentage=1.0
    ):
        matrix = self.filterMatrix
        if not matrix:
            print("Empty matrix")
            return []

        rows = len(matrix)
        cols = max(len(row) for row in matrix)

        center_r = (rows - 1) / 2
        center_c = (cols - 1) / 2
        radius = ((min(rows, cols) - 1) / 2) * size_percentage

        for r in range(rows):
            for c in range(len(matrix[r])):
                matrix[r][c] = random.randint(
                    self.bottom_range,
                    self.top_range
                )

        return matrix

    def create_heat_map(
        self,
        twod_array,
        output_file="output.png",
        img_name="BIR_TIFF.png"
    ):
        img = Image.open(img_name)
        img = img.convert("RGBA")
        self.width, self.height = img.size

        self.filterMatrix = self.create_filter(twod_array)

        overlay = Image.new("RGBA", img.size, (0, 0, 0))

        result = Image.alpha_composite(
            img,
            self.RGB_Set(
                overlay,
                self.height,
                self.width,
                self.filterMatrix,
                self.bottom_range,
                self.top_range
            )
        )

        result.save(output_file)

        return self.filterMatrix

    # Sets each overlay pixel to an RGB value based on the range.
    @staticmethod
    def RGB_Set(overlay, height, width, new_array, bottom, top):
        pixels_over = overlay.load()

        for y in range(0, height - 1):
            for x in range(0, width):
                try:
                    charge = new_array[x][y]
                    total = (top - bottom)
                except Exception as e:
                    print(y, x)

                if charge < 0.01 * total + bottom:
                    red = 127
                    green = 127
                    blue = 127

                elif charge < 0.25 * total + bottom:
                    red = 0
                    green = int(
                        charge / (0.25 * total + bottom) * 255
                    )
                    blue = 255

                elif charge < 0.5 * total + bottom:
                    red = 0
                    green = 255
                    blue = int(
                        -1 * (
                            (charge - (0.25 * total + bottom))
                            / (0.25 * total + bottom) + 1
                        ) * 255
                    )

                elif charge < 0.75 * total + bottom:
                    red = int(
                        (
                            (charge - (0.5 * total + bottom))
                            / (0.25 * total + bottom)
                        ) * 255
                    )
                    green = 255
                    blue = 0

                else:
                    red = 255
                    green = int(
                        (
                            -1 * (
                                (charge - (0.75 * total + bottom))
                                / (0.25 * total + bottom)
                            ) + 1
                        ) * 255
                    )
                    blue = 0

                pixels_over[x, y] = (red, green, blue, 100)

        return overlay

    def update_filter(self, x, y, amt):
        for i in range(x - 2, x + 3):
            for j in range(y - 2, y + 3):
                self.filterMatrix[j][i] += amt * (
                    math.pow(
                        2,
                        -0.5 * (abs(i - x) + abs(j - y))
                    )
                )

        img = Image.open(self.output_file)
        img = img.convert("RGBA")
        self.width, self.height = img.size
        overlay = Image.new("RGBA", img.size, (0, 0, 0))

        result = Image.alpha_composite(
            img,
            self.RGB_Set(
                overlay,
                self.height,
                self.width,
                self.filterMatrix,
                self.bottom_range,
                self.top_range
            )
        )

        result.save(self.output_file)

        return self.filterMatrix

    @staticmethod
    def spread(twod_array, y, x):
        break_again = False
        sum = 0

        for i in range(x - 2, x + 3):
            for j in range(y - 2, y + 3):
                try:
                    if (
                        i >= 0
                        and j >= 0
                        and i < len(twod_array)
                        and j < len(twod_array)
                    ):  
                        sum += twod_array[j][i] * float((
                            math.pow(
                                2,
                                -0.5 * (abs(i - x) + abs(j - y))
                            )
                        ))
                except Exception as e:
                    print(e)
                    # print("coordinates", j, i)
                    pass

            if break_again:
                break

        avg = sum // 9

        return avg

    @property
    def CSV_PATH(self):
        return self._CSV_PATH

    @CSV_PATH.setter
    def CSV_PATH(self, value):
        self._CSV_PATH = value

    @property
    def filterMatrix(self):
        return self._filterMatrix

    @filterMatrix.setter
    def filterMatrix(self, value):
        self._filterMatrix = value

    @property
    def originalTrack(self):
        return self._originalTrack

    @originalTrack.setter
    def originalTrack(self, value):
        self._originalTrack = value

    @property
    def originalTrack_name(self):
        return self._originalTrack_name

    @originalTrack_name.setter
    def originalTrack_name(self, value):
        self._originalTrack_name = value

    @property
    def heatMap(self):
        return self._heatMap

    @heatMap.setter
    def heatMap(self, value):
        self._heatMap = value

    @property
    def dataType(self):
        return self._dataType

    @dataType.setter
    def dataType(self, value):
        self._dataType = value

    @property
    def min_elevation(self):
        return self._min_elevation

    @min_elevation.setter
    def min_elevation(self, value):
        self._min_elevation = value

    @property
    def max_elevation(self):
        return self._max_elevation

    @max_elevation.setter
    def max_elevation(self, value):
        self._max_elevation = value


# Heatmap_inst1 = HeatMap(
#     "./BIR_CSV.csv",
#     "./BIR_CSV.csv",
#     "BIr",
#     None,
#     "Charge",
#     0,
#     100,
#     "BIR_TIFF.tiff"
# )

# HeatMap.matrix_test(Heatmap_inst1)
# Heatmap_inst1.create_filter(
#     Heatmap_inst1.filterMatrix
# )

# x, y = HeatMap.coordinate_finder(Heatmap_inst1, 46.416981, -94.276917)

# Heatmap_inst1.update_filter(x, y, 50)

