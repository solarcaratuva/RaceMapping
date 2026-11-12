from PIL import Image
import csv
import math
import utm
import random
import copy
import numpy as np
from scipy.interpolate import griddata

class HeatMap:
    def __init__(
        self,
        originalTrack,
        originalTrack_name: str,
        heatMap,
        dataType: str,
        bottom_range,
        top_range,
        output_file,
        img_name
    ):
        self.CSV_PATH = originalTrack
        self.filterMatrix = list(list())
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
        self.width = 0
        self.height = 0
        self.img_name = img_name

        
        self.CSV_to_MATRIX()

        
    # returns and updates self.filterMatrix as a matrix populated with a coordinate tuple (x,y) for all points in a given CSV.
    def CSV_to_MATRIX(self):
            # Iterates through track CSV, finds width and height of track image (takes max dimension of the CSV or img file to verify bounds).
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
                    pass
            with Image.open(self.img_name) as img:
                max_row = max(max_row, img.size[1] - 1)
                max_col = max(max_col, img.size[0] - 1)

            # Initializes empty matrix of found dimensions.
            matrix = [
                [None for _ in range(max_col + 1)]
                for _ in range(max_row + 1)
            ]

            # Updates row_count & column_count
            self.row_count = max_row + 1
            self.column_count = max_col + 1

            # Updates left_bound and top_bound attributes
            # Updates each matrix location from None to a tuple describing the appropriate coordinate location (x, y).
            for row in rows:
                if row[0] == '1':
                    self.left_bound = float(row[1])
                    self.top_bound = float(row[2])
                try:
                    if type(int(row[0])) != type("str"):
                        #change depending on the csv file
                        x = float(row[1])
                        y = float(row[2])
                        col = int(row[5])
                        r = int(row[6])
                        matrix[r][col] = (x, y)                    
                except Exception as e:
                    pass           
                
            # Updates the self.filterMatrix attribute to matrix.
            # Returns matrix.
            self.filterMatrix = matrix
            return matrix

    # For given matrix element (coordinate), returns weighted average value for that point, based on surrounding points
    @staticmethod
    def spread(twod_array, y, x):
        total = 0.0
        weight_sum = 0.0
        # Iterates through all points in a 2 pixel radius from the input coordinates, if they are within bounds.
        for i in range(x - 2, x + 3):
            for j in range(y - 2, y + 3):
                if 0 <= i < len(twod_array[0]) and 0 <= j < len(twod_array):
                    # Calculates intensity multipliers for each iterated point in range; intensity has base 2 exponential decay per pixels away from center coord.
                    w = math.pow(2, -0.5 * (abs(i - x) + abs(j - y)))

                    # Calculates sum of all intensity values in the 2 pixel radius.
                    total += twod_array[j][i] * w

                    # Calculates sum of all intensity multipliers (weights) 
                    weight_sum += w

        # returns weighted average value for input point
        return total / weight_sum

    # Given matrix of weighted average intensities/values, finds the min and max values to save as attributes. 
    def set_range_from_matrix(self, matrix):
        # finds min and max values of whole matrix
        low = min(min(row) for row in matrix)
        high = max(max(row) for row in matrix)
        if high == low:
            # Avoid a zero-width range
            high = low + 1
        # Saves min and max as attributes
        self.min_elevation = low
        self.max_elevation = high
        self.bottom_range = low
        self.top_range = high

    # Uses spread() on all points in the matrix, converts filterMatrix data from coordinate tuples to intensities
    def create_filter(self, twod_array):
        new_array = copy.deepcopy(twod_array)

        # Iterates through all matrix elements
        for y in range(len(twod_array)):
            for x in range(len(twod_array[0])):
                # Calls spread() to get weighted average intensity for each point
                new_array[y][x] = self.spread(twod_array, y, x)

        # Replaces per-point array of coordinate tuples (x,y) with per-point array of weighted average intensities.
        self.filterMatrix = new_array

        # Saves min and max values/intensities
        self.set_range_from_matrix(new_array)
        return new_array


    # Given coordinates in bounds, find row and column indexes.
    def coordinate_finder(self, lat, lon):
        # Converts degree-based coordinates to meter-based (utm) coordinates
        utm_lat_lon = utm.from_latlon(lat, lon)
        easting, northing = utm_lat_lon[0], utm_lat_lon[1]

        # Takes UTM coordinates, subtracts from the minimum (top/left) bounds, and divides by 3 (meter intervals)
        row_location = -(northing - self.top_bound) / 3
        column_location = (easting - self.left_bound) / 3

        # Truncates and converts to integer for indexing.
        row_location = int(row_location // 1)
        column_location = int(column_location // 1)

        # Returns row and column indexes in a tuple, if they're in bounds.
        if 0 <= column_location < self.row_count and 0 <= row_location < self.column_count:
            return (int(column_location), int(row_location))
        else:
            return (None, None)

    # Returns a same-size matrix of elevation values (with interpolated values between if not enough per pixel).
    # If no elevation file given, uses random values.
    def matrix_test(self, path_elevation=None):
        # Get the matrix stored in the object
        matrix = self.filterMatrix

        # Check whether the matrix is empty
        if not matrix:
            print("Empty matrix")
            return []

        # Get the number of rows and columns in the matrix
        rows, cols = len(matrix), len(matrix[0])

        # If an elevation file is provided, populate the matrix using its data
        if path_elevation:
            # Dictionary to store elevation values using matrix coordinates (row, column)
            points = {}

            # Open the elevation CSV file for reading
            with open(path_elevation, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)

                # Skip the first row because it contains column headers
                next(reader, None)

                # Read each row in the CSV file
                for row in reader:
                    # Skip empty rows
                    if not row:
                        continue

                    # Extract elevation, longitude, and latitude from the CSV columns
                    elevation = float(row[1])
                    lon = float(row[2])
                    lat = float(row[3])

                    # Convert geographic coordinates into matrix indices
                    r, c = self.coordinate_finder(lat, lon)

                    # Ignore points that fall outside the matrix boundaries
                    if r is None or c is None or r >= rows or c >= cols:
                        continue

                    # Store the elevation at its corresponding matrix position
                    points[(r, c)] = elevation

            print("Placed", len(points), "points")

            # Check whether any elevation points were successfully mapped
            if not points:
                print("No points landed in the matrix; check bounds/coordinates")
                return matrix

            # If some matrix cells are missing elevation values, interpolate them
            if len(points) < rows * cols:

                # Convert the matrix coordinates and elevation values into NumPy arrays
                pts = np.array(list(points.keys()))
                vals = np.array(list(points.values()))

                # Generate coordinate grids covering every matrix cell
                grid_r, grid_c = np.mgrid[0:rows, 0:cols]

                # Apply linear interpolation to estimate missing elevation values
                filled = griddata(pts, vals, (grid_r, grid_c), method="linear")

                # Apply nearest-neighbor interpolation as a fallback
                # for cells where linear interpolation produces NaN values
                nearest = griddata(pts, vals, (grid_r, grid_c), method="nearest")

                # Replace NaN values in the linear interpolation results
                # with the corresponding nearest-neighbor values
                filled = np.where(np.isnan(filled), nearest, filled)

                # Copy the interpolated elevation values into the original matrix
                for r in range(rows):
                    for c in range(cols):
                        matrix[r][c] = float(filled[r][c])

            else:
                # If every matrix cell has an elevation point,
                # directly assign the elevation values without interpolation
                for (r, c), elevation in points.items():
                    matrix[r][c] = elevation

        else:
            # If no elevation file is provided, fill the matrix with random values
            # between the configured minimum and maximum elevation ranges
            for r in range(rows):
                for c in range(cols):
                    matrix[r][c] = random.randint(
                        self.bottom_range,
                        self.top_range
                    )

        # Update the object's minimum and maximum range using the populated matrix
        self.set_range_from_matrix(matrix)

        return matrix


    # Creates a new overlaying image using RGB_Set() for intensity coloring.
    def create_heat_map(self):
        img = Image.open(self.img_name)
        img = img.convert("RGBA")

        self.width, self.height = img.size

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))

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

    # Sets each overlay pixel to an RGB value based on the value of each coordinate, relative to the range.
    # Each new pixel color has an opacity of 100 (out of 255), so original track image can be seen underneath.
    @staticmethod
    def RGB_Set(overlay, height, width, new_array, bottom, top):
        pixels_over = overlay.load()
        total = max(top - bottom, 1)
        rows, cols = len(new_array), len(new_array[0])

        for y in range(min(height, cols)):
            for x in range(min(width, rows)):
                frac = (new_array[x][y] - bottom) / total

                if frac < 0.01:
                    red, green, blue = 127, 127, 127
                elif frac < 0.25:
                    red, green, blue = 0, int(frac / 0.25 * 255), 255
                elif frac < 0.5:
                    red, green, blue = 0, 255, int((1 - (frac - 0.25) / 0.25) * 255)
                elif frac < 0.75:
                    red, green, blue = int((frac - 0.5) / 0.25 * 255), 255, 0
                else:
                    red = 255
                    green = max(0, int((1 - (frac - 0.75) / 0.25) * 255))
                    blue = 0

                pixels_over[x, y] = (red, green, blue, 100)

        return overlay

    def update_filter(self, x, y, amt):
        for i in range(x - 2, x + 3):
            for j in range(y - 2, y + 3):
                self.filterMatrix[i][j] += amt * (
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
    def output_file(self):
        return self._output_file

    @output_file.setter
    def output_file(self, value):
        self._output_file = value


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
    def left_bound(self):
        return self._left_bound

    @left_bound.setter
    def left_bound(self, value):
        self._left_bound = value


    @property
    def top_bound(self):
        return self._top_bound

    @top_bound.setter
    def top_bound(self, value):
        self._top_bound = value


    @property
    def row_count(self):
        return self._row_count

    @row_count.setter
    def row_count(self, value):
        self._row_count = value


    @property
    def column_count(self):
        return self._column_count

    @column_count.setter
    def column_count(self, value):
        self._column_count = value


    @property
    def bottom_range(self):
        return self._bottom_range

    @bottom_range.setter
    def bottom_range(self, value):
        self._bottom_range = value


    @property
    def top_range(self):
        return self._top_range

    @top_range.setter
    def top_range(self, value):
        self._top_range = value


    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        self._width = value


    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, value):
        self._height = value


    @property
    def img_name(self):
        return self._img_name

    @img_name.setter
    def img_name(self, value):
        self._img_name = value

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

def random_coords():
    Top = 46.42361754
    Bottom = 46.40898986
    Left = -94.28528025
    Right = -94.26578155
    return [(random.uniform(46.40898986,46.42361754), random.uniform(-94.28528025,-94.26578155)) for x in range(200)]


Heatmap_inst1 = HeatMap(
            originalTrack =  "./OIR_CSV.csv",
            output_file = "./OIR_TIFF-heatmap.tiff",
            originalTrack_name = "OIR",
            heatMap = None,
            dataType = "Elevation",
            bottom_range = 0,
            top_range = 1000,
            img_name = "OIR_TIFF.tiff"
)

# changes the tuples in the matrix to int (for create_filter and update_filter)
HeatMap.matrix_test(Heatmap_inst1, path_elevation="./OIR_ELEV_CSV.csv")

# create_filter only creates the matrix that the update_filter will read and assign RGB_val
Heatmap_inst1.create_filter(
    Heatmap_inst1.filterMatrix
)

Heatmap_inst1.create_heat_map()

# for x_coord, y_coord in random_coords():
    
#     x, y = HeatMap.coordinate_finder(Heatmap_inst1, x_coord, y_coord)
#     if x == None or y == None:
#         continue

#     #Produces updates the actual img
#     Heatmap_inst1.update_filter(x, y, 50)