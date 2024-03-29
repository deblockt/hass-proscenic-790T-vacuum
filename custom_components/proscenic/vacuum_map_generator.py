import base64
import struct
import svgwrite


cell_size=5
min_image_height=250
min_image_width=450

def build_map(m, track):
    inp = base64.b64decode(m)
    d = struct.unpack('<' + 'B' * (len(inp)), inp)
    full = [['.' for i in range(100)] for j in range(110)]
    akt = 0
    i = 0

    def placebyte(by):
        pair = by
        if pair & 0b10 == 0b10:
            full[((akt + 3) // 100)][((akt + 3) % 100)] = '_'
        elif pair & 0b01 == 0b01:
            full[((akt + 3) // 100)][((akt + 3) % 100)] = '0'
        pair = by >> 2
        if pair & 0b10 == 0b10:
            full[((akt + 2) // 100)][((akt + 2) % 100)] = '_'
        elif pair & 0b01 == 0b01:
            full[((akt + 2) // 100)][((akt + 2) % 100)] = '0'
        pair = by >> 4
        if pair & 0b10 == 0b10:
            full[((akt + 1) // 100)][((akt + 1) % 100)] = '_'
        elif pair & 0b01 == 0b01:
            full[((akt + 1) // 100)][((akt + 1) % 100)] = '0'
        pair = by >> 6
        if pair & 0b10 == 0b10:
            full[(akt // 100)][(akt % 100)] = '_'
        elif pair & 0b01 == 0b01:
            full[(akt // 100)][(akt % 100)] = '0'

    while i < len(d):
        if i >= 9:
            if d[i] & 0b11000000 == 0b11000000:
                mul = d[i] & 0b00111111
                if d[i + 1] & 0b11000000 == 0b11000000:
                    i += 1
                    mul <<= 6
                    mul |= (d[i] & 0b00111111)
                for rep in range(mul):
                    placebyte(d[i + 1])
                    akt += 4
                i += 1
            else:
                placebyte(d[i])
                akt = akt + 4
        i += 1

    # print("\n".join(["".join(map(str,fline)) for fline in full]))

    wallx = []
    wally = []
    floorx = []
    floory = []
    for idy,l in enumerate(full):
        for idx,r in enumerate(l):
            if r == '0':
                wallx.append(idx)
                wally.append(idy)
            if r == '_':
                floorx.append(idx)
                floory.append(idy)

    inp = base64.b64decode(track)
    path = struct.unpack('<' + 'b'*(len(inp)-4), inp[4:])

    if len(wallx) == 0 or len(wally) == 0:
        return

    min_x=min(wallx)
    min_y=min(wally)
    map_width=(max(wallx) - min_x) * cell_size
    map_height=(max(wally) - min_y) * cell_size

    if map_width < min_image_width:
        min_x = min_x - ((min_image_width - map_width) / 2) // cell_size
        map_width = min_image_width
    if map_height < min_image_height:
        min_y = min_y - ((min_image_height - map_height) / 2) // cell_size
        map_height = min_image_height

    dwg = svgwrite.Drawing(size=(map_width, map_height))

    for i in range(len(wallx)):
        dwg.add(dwg.rect(insert=((wallx[i] - min_x) * cell_size, map_height - ((wally[i] - min_y) * cell_size)), size=(cell_size, cell_size), fill='#000000', fill_opacity=0.7))

    for i in range(len(floorx)):
        dwg.add(dwg.rect(insert=((floorx[i] - min_x) * cell_size, map_height - ((floory[i] - min_y) * cell_size)), size=(cell_size, cell_size), fill='#000000', fill_opacity=0.3))

    draw_path = [(((coord - min_x) * cell_size) + (cell_size / 2) if i % 2 == 0 else (map_height - ((coord - min_y) * cell_size)) + (cell_size / 2)) for i, coord in enumerate(path)]
    dwg.add(dwg.circle(center = (draw_path[-2], draw_path[-1]), r = (cell_size / 2), fill='#000000', fill_opacity=0.65))

    dwg_path = dwg.path(['M{},{}'.format(draw_path[0], draw_path[1])], fill="white", fill_opacity=0, stroke = 'black', stroke_opacity = 0.6)

    for i in range(len(draw_path) // 2):
        dwg_path.push('L{},{}'.format(draw_path[2*i], draw_path[2*i+1]))

    dwg.add(dwg_path)

    return dwg.tostring()

#m = "AAAAAAAAZABkwvIAFUDXABXCVUDVABaqwlXVAFbCqqlA1ABmw6pUVUDSAGbDqqTCVVDRAFbDqqVqqpDRAFbDqqVVqJDRAFqqqaqlVqSQ0QBaqpZqwqqkkNEAWqqZmsKqpJDRAFqqmWrCqqSQ0QAVVapawqqkkNIABVVawqqkkNQAFsKqpJDUABbCqqWQ1AAWwqqplNQAFsOqpdQAGsOqqUDTABrDqppQ0wAaw6qmkNMAFWrCqplQ0wAFw6qZQNMABcOqmkDTAAXDqplA0wAFw6pJQNMABcOqSdQABalqqkpA0wBWqVqqolDTAGqkFqqmkNIAAWqkBqqklNIAAaqQBqqkkNIAAaqQBqqkkNIAAZqQGqqklVTRAAGqkCqqpaqk0QABqpAqw6qoFNAAAaqQFqqlqpqk0AAGqpAqqqWqkKTQAAaqkCrDqlWU0AAGqpQaqsKWqZDQAAaqpGqqlqqpoNAABaqpasKqpalo0AABWqqawqpWqmqA0AAaxKpVwqrRABVVaqpaw6rSAAFVmcSq0wABVVbCVVbVAAVAAALYAALYAAVA0P0A"
#track = "ASg+ATI0NDQrNCs1KzM2MzYyNzIgMiEyHDIcMRoxIDEfMR4wGTAZLxgvHS8cLhcuFy0cLRwsFywYKxwrHCoYKhgpHCkcKBgoGCccJxwmGSYZJR0lHSQZJBojHiMdIhsiHiIeIRshHyEfICAgGyAcHxsfKB8oHhseHB4bHhsdKB0oHBwcHBspGygaGhoaGSgZJxgaGBoXJhclFhoWGhUlFSUUGhQaEyUTJRIZEhkRJRElEBgQGA8XDyUPJQ4mDh4OHw0fDh8NIA4hDiINJg0lDCIMIQ0hDCENHA4NDg0NHA0cDA0MDQsaCxkKDgoOCRcJEQkPCA4IDg8NDxYPFBANEA0RFBEUEhESDxEhICcgJyEgISEiJyInIygjIiMjJCkkKSUjJSMmKSYpJyMnIygpKCkpIikiKiEqLiouKy8rLyowKjArKyssKywsMCwvLC8tIS0iLSEtIi4pLiguKC8hLyEwLTAtLysvMi8yMDAwMDEzMTAxMzE1MjUxMS4yLiwuKSwpKysqLSooLCsuKzEiMSIzLjMqNCk0NjQkNCQzIDMgMhoyGjEZMRkwGDAXLxctFy4XLBgqGCYZJhgmGCUZJRkkGiQcIhwbGhsaGhsYGxUaFBoSGRIYEBgRFxAWERcRFhIWExcTExMTEg4SDg4PDg8JFAkUChoKHAwdDB0OHg4eDx8PHxAfDx8QIBAhDiENIw0hDSEOIg0oDScNKA0oGCkYKRkqGSoaKxorGywbKxwqHCodKx0qHSoeKx4qHiohKiAqISshKyIqIisjKyQtJCwlLCgtKCwoLCkxKTEqMioyKzQrNCw1LDQsNSw1KzUsNCw0LzUvNTA2MDYyNzM3Nw=="

#build_map(m, track, 'map.svg')

#m = "AAAAAAAAZABk0vYAxqqVQNAAAceqQNAAAcKqmsOqqUDQAAHCqpDXAAKg0ucA"
#track = "AQQHADIxMzEYMRgyIDIgMx8z"
#build_map(m, track, 'map.svg')
