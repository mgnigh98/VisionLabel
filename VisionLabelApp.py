import os
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import filedialog, scrolledtext
from tkinter.messagebox import askyesno
from PIL import Image, ImageTk
from sarpy.geometry import point_projection
from sarpy.io.complex.sicd import SICDReader
from sarpy.visualization.remap import Density
from sarpy.utils import chip_sicd

remap = Density()

class VisionLabelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SICD Viewer")
        self.image_label = tk.Label(self.root)  # No need for this label
        self.image_label.pack()  # Remove this line
        self.current_image_index = None
        self.image_paths = []

        menu_bar = tk.Menu(root)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Open Image", command=self.open_image)
        file_menu.add_command(label="Exit", command=root.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)
        root.config(menu=menu_bar)

        # Add label for displaying file name
        self.text_box = scrolledtext.ScrolledText(self.root, wrap=tk.NONE, font=("Helvetica", 12), height=.5, width=150)
        self.text_box.pack(expand=False)

        top_frame = tk.Frame(root)
        top_frame.pack(side='top')

        radio_frame = tk.Frame(top_frame)
        radio_frame.pack(side=tk.RIGHT)

        self.radio = tk.IntVar()
        self.r0 = tk.Radiobutton(radio_frame, text="Boxes", variable=self.radio, value=0)
        self.r0.pack(anchor= tk.W)
        self.r1 = tk.Radiobutton(radio_frame, text="Lines", variable=self.radio, value=1)
        self.r1.pack(anchor= tk.W)
        self.r2 = tk.Radiobutton(radio_frame, text="Pan", variable=self.radio, value=2)
        self.r2.pack(anchor= tk.W)

        self.radio.set(0)

        # Create buttons for next and previous images
        self.prev_button = tk.Button(self.root, text="Prev", command=self.prev_image)
        self.prev_button.pack(side=tk.LEFT)
        self.next_button = tk.Button(self.root, text="Next", command=self.next_image)
        self.next_button.pack(side=tk.RIGHT)
        
        button_frame = tk.Frame(root)
        button_frame.pack(side='top')
        remove_button = tk.Button(button_frame, text="Remove Image", command=self.remove_image)
        remove_button.pack(side=tk.RIGHT)
        grid_chip_button = tk.Button(button_frame, text="Create PNG Grid", command=self.png_grid_chip)
        grid_chip_button.pack(side=tk.LEFT)
        chip_button = tk.Button(button_frame, text="Export Chips", command=self.chip)
        chip_button.pack(side=tk.LEFT)
        chip_options_frame = tk.Frame(button_frame)
        chip_options_frame.pack(side=tk.RIGHT)
        self.chip_png_var = tk.IntVar()
        self.chip_sicd_var = tk.IntVar()
        self.chip_png_box = tk.Checkbutton(chip_options_frame, variable=self.chip_png_var, text="Chip to PNG", onvalue=1, offvalue=0)
        self.chip_png_box.pack(side=tk.TOP)
        self.chip_sicd_box = tk.Checkbutton(chip_options_frame, variable=self.chip_sicd_var, text="Chip to SICD", onvalue=1, offvalue=0)
        self.chip_sicd_box.pack(side=tk.BOTTOM)
        

        check_box_frame = tk.Frame(top_frame)
        check_box_frame.pack(side=tk.LEFT)
        
        self.csv_box = tk.IntVar()
        self.pix_box = tk.IntVar()
        self.bb_button = tk.IntVar()
        self.txt = tk.StringVar()
        self.txt.set(0)
        self.export_csv_box = tk.Checkbutton(check_box_frame, variable=self.csv_box, text="Export Rectangles CSV", onvalue=1, offvalue=0)
        self.export_csv_box.pack(side=tk.RIGHT)

        self.textbox_label = tk.Label(text="Class Label")
        self.textbox_label.pack(side=tk.TOP)
        self.textbox = tk.Entry(text="Class Label", textvariable=self.txt)
        self.textbox.pack(side=tk.TOP)
        self.export_pix_box = tk.Checkbutton(check_box_frame, variable=self.pix_box, text="Export Rectangles TXT", onvalue=1, offvalue=0)
        self.export_pix_box.pack(side=tk.LEFT)
        self.import_bb_button = tk.Checkbutton(check_box_frame, variable=self.bb_button, text="Import Bounding Boxes", onvalue=1, offvalue=0, command=self.import_bounding_boxes)
        self.import_bb_button.pack(side=tk.TOP)

        self.canvas = tk.Canvas(self.root, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=tk.YES)

        # Bind events for zooming and panning
        # self.canvas.bind("<MouseWheel>", self.zoom)
        self.canvas.bind('<MouseWheel>', self.wheel)  # with Windows and MacOS, but not Linux
        self.canvas.bind('<Button-5>',   self.wheel)  # only with Linux, wheel scroll down
        self.canvas.bind('<Button-4>',   self.wheel)  # only with Linux, wheel scroll up
        
        # Bind arrow keys for navigation
        self.root.bind("<Left>", self.prev_image)
        self.root.bind("<Right>", self.next_image)

        for i in range(10):
            self.root.bind(str(i), self.num_key)

        self.root.bind('<Up>', self.class_label_up)
        self.root.bind('<Down>', self.class_label_down)


        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<ButtonPress-2>", self.middle_click)
        self.canvas.bind("<ButtonPress-3>", self.right_click)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        # Initial zoom level and pan offset
        # self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0

        # Initialize image and image ID
        self.image = None
        self.image_id = None

        # Rectangle drawing variables
        self.csv = None
        self.rect = None
        self.start_x = None
        self.start_y = None
        # List to keep track of drawn rectangles
        self.shapes = []
        self.shape_type = []

    def num_key(self, event):
        self.txt.set(event.char)
    def class_label_up(self, event):
        self.txt.set(int(self.txt.get())+1)
    def class_label_down(self, event):
        self.txt.set(int(self.txt.get())-1)

    def get_shape_coords(self, shape):
        w, h = self.image.width, self.image.height
        # print(w, h)
        x, y = self.canvas.coords(self.container)[0], self.canvas.coords(self.container)[1]
        x1,y1,x2,y2 = self.canvas.coords(shape)
        coords = np.array([x1-x, y1-y, x2-x, y2-y])/self.imscale
        coords[0] = np.max([0, coords[0]])
        coords[1] = np.max([0, coords[1]])
        coords[2] = np.min([w, coords[2]])
        coords[3] = np.min([h, coords[3]])
        return coords

    
    def chip(self):
        for i, shape in enumerate(self.shapes):
            if self.shape_type[i] == 0:
                shape_coords = self.get_shape_coords(shape)
                file_path = self.image_paths[self.current_image_index]
                dir_path = os.path.dirname(file_path)
                file_name = os.path.basename(file_path)
                if self.chip_png_var.get():
                    os.makedirs(f"{dir_path}/pngs", exist_ok=True)
                    cropped_image = self.image.crop(shape_coords)
                    shape_coords = [int(i) for i in shape_coords]
                    cropped_image.save(f"{dir_path}/pngs/{file_name.split('.')[0]}_{shape_coords[0]}-{shape_coords[2]}_{shape_coords[1]}-{shape_coords[3]}.png")
                    # os.rename(f"{dir_path}/pngs/{file_name.split('.')[0]}.png",f"{dir_path}/pngs/{file_name.split('.')[0]}{i}.png")
                if self.chip_sicd_var.get():
                    os.makedirs(f"{dir_path}/sicds", exist_ok=True)
                    chip_sicd.create_chip(self.sicd, out_directory=f"{dir_path}/sicds", 
                                          row_limits=[shape_coords[0],shape_coords[2]], col_limits=[shape_coords[1], shape_coords[3]], check_existence=False)
    
    def png_grid_chip(self, grid_size=512):

        w, h = self.image.width, self.image.height
        sub_grid = grid_size//2
        w_, h_ = w//sub_grid, h//sub_grid
        file_path = self.image_paths[self.current_image_index]
        dir_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        os.makedirs(f"{dir_path}/{file_name}_grid")
        for j in range(h_-1):
            for i in range(w_-1):
                left = i*sub_grid
                upper =j*sub_grid
                right = left+grid_size
                lower = upper+grid_size
                cropped_image = self.image.crop((left, upper, right, lower))
                cropped_image.save(f"{dir_path}/{file_name}_grid/{file_name.split('.')[0]}_{j}_{i}.png")
                # cropped_image.save(f"{dir_path}/{file_name}_grid/{file_name.split('.')[0]}_{left}-{right}_{upper}-{lower}.png")
        if w%sub_grid != 0:
            right = w
            left = right-grid_size
            i+=1
            for j in range(h_-1):
                upper =j*sub_grid
                lower = upper+grid_size
                cropped_image = self.image.crop((left, upper, right, lower))
                cropped_image.save(f"{dir_path}/{file_name}_grid/{file_name.split('.')[0]}_{j}_{i}.png")
                # cropped_image.save(f"{dir_path}/{file_name}_grid/{file_name.split('.')[0]}_{left}-{right}_{upper}-{lower}.png")
        if h%sub_grid!= 0:
            lower = h
            upper =lower-grid_size
            j+=1
            for i in range(w_-1):
                left = i*sub_grid
                right = left+grid_size
                cropped_image = self.image.crop((left, upper, right, lower))
                cropped_image.save(f"{dir_path}/{file_name}_grid/{file_name.split('.')[0]}_{j}_{i}.png")
                # cropped_image.save(f"{dir_path}/{file_name}_grid/{file_name.split('.')[0]}_{left}-{right}_{upper}-{lower}.png")
        if (h%sub_grid!= 0) and (w%sub_grid != 0):
            right=w
            lower=h
            left = right-grid_size
            upper =lower-grid_size
            i+=1
            cropped_image = self.image.crop((left, upper, right, lower))
            cropped_image.save(f"{dir_path}/{file_name}_grid/{file_name.split('.')[0]}_{j}_{i}.png")
            # cropped_image.save(f"{dir_path}/{file_name}_grid/{file_name.split('.')[0]}_{left}-{right}_{upper}-{lower}.png")


    def wheel(self, event):
        ''' Zoom with mouse wheel '''
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.bbox = self.canvas.bbox(self.container)  # get image area
        if self.bbox[0] < x < self.bbox[2] and self.bbox[1] < y < self.bbox[3]: pass  # Ok! Inside the image
        else: return  # zoom only inside image area
        scale = 1.0
        # Respond to Linux (event.num) or Windows (event.delta) wheel event
        if event.num == 5 or event.delta == -120:  # scroll down
            i = min(self.width, self.height)
            if int(i * self.imscale) < 30: return  # image is less than 30 pixels
            self.imscale /= self.delta
            scale        /= self.delta
        if event.num == 4 or event.delta == 120:  # scroll up
            i = min(self.canvas.winfo_width(), self.canvas.winfo_height())
            if i < self.imscale: return  # 1 pixel is bigger than the visible area
            self.imscale *= self.delta
            scale        *= self.delta
        self.canvas.scale('all', x, y, scale, scale)  # rescale all canvas objects
        self.update_image()
        
    
    def update_image(self, event=None):
        # if self.image:
        #     self.width = self.image.width * self.zoom_level
        #     self.height = self.image.height * self.zoom_level
        #     new_width = int(self.width)
        #     new_height = int(self.height)

        #     # Resize the image
        #     resized_image = self.image.resize((new_width, new_height), Image.LANCZOS)
        #     self.image_tk = ImageTk.PhotoImage(resized_image)

        #     # Update the image on canvas
        #     if self.image_id:
        #         self.canvas.itemconfig(self.image_id, image=self.image_tk)
        #         self.canvas.configure(scrollregion=(0, 0, new_width, new_height))
        #         self.canvas.xview_moveto(self.offset_x / new_width)
        #         self.canvas.yview_moveto(self.offset_y / new_height)
        ''' Show image on the Canvas '''
        bbox1 = self.canvas.bbox(self.container)  # get image area
        # Remove 1 pixel shift at the sides of the bbox1
        bbox1 = (bbox1[0] + 1, bbox1[1] + 1, bbox1[2] - 1, bbox1[3] - 1)
        bbox2 = (self.canvas.canvasx(0),  # get visible area of the canvas
                 self.canvas.canvasy(0),
                 self.canvas.canvasx(self.canvas.winfo_width()),
                 self.canvas.canvasy(self.canvas.winfo_height()))
        bbox = [min(bbox1[0], bbox2[0]), min(bbox1[1], bbox2[1]),  # get scroll region box
                max(bbox1[2], bbox2[2]), max(bbox1[3], bbox2[3])]
        if bbox[0] == bbox2[0] and bbox[2] == bbox2[2]:  # whole image in the visible area
            bbox[0] = bbox1[0]
            bbox[2] = bbox1[2]
        if bbox[1] == bbox2[1] and bbox[3] == bbox2[3]:  # whole image in the visible area
            bbox[1] = bbox1[1]
            bbox[3] = bbox1[3]
        self.canvas.configure(scrollregion=bbox)  # set scroll region
        x1 = max(bbox2[0] - bbox1[0], 0)  # get coordinates (x1,y1,x2,y2) of the image tile
        y1 = max(bbox2[1] - bbox1[1], 0)
        x2 = min(bbox2[2], bbox1[2]) - bbox1[0]
        y2 = min(bbox2[3], bbox1[3]) - bbox1[1]
        if int(x2 - x1) > 0 and int(y2 - y1) > 0:  # show image if it in the visible area
            x = min(int(x2 / self.imscale), self.width)   # sometimes it is larger on 1 pixel...
            y = min(int(y2 / self.imscale), self.height)  # ...and sometimes not
            image = self.image.crop((int(x1 / self.imscale), int(y1 / self.imscale), x, y))
            imagetk = ImageTk.PhotoImage(image.resize((int(x2 - x1), int(y2 - y1))))
            imageid = self.canvas.create_image(max(bbox2[0], bbox1[0]), max(bbox2[1], bbox1[1]),
                                               anchor='nw', image=imagetk)
            self.canvas.lower(imageid)  # set image into background
            self.canvas.imagetk = imagetk  # keep an extra reference to prevent garbage-collection


    def open_image(self):
        self.clear_rect()
        file_paths = filedialog.askopenfilenames(filetypes=[("SAR Images", "*.ntf *.nitf"), ("Pictures", "*.jpg *.jpeg *.png")])
        if len(file_paths) >1:
            self.image_paths = list(file_paths)
            self.current_image_index = 0
            self.show_current_image()
        elif len(file_paths) ==1:
            self.directory = os.path.dirname(file_paths[0])
            file_type = file_paths[0].split('.')[-1]
            self.image_paths = [f"{self.directory}/{file}" for file in os.listdir(self.directory) if os.path.isfile(os.path.join(self.directory, file)) and file.endswith(file_type)]
            self.current_image_index = self.image_paths.index(file_paths[0])
            self.show_current_image()


    def show_current_image(self):
        if self.current_image_index is not None:

            file_path = self.image_paths[self.current_image_index]
            if file_path.endswith(('.ntf', '.nitf')):
                self.sicd = SICDReader(file_path)
                sar_image = self.sicd[:]
                self.image = Image.fromarray(remap(sar_image))
                self.chip_sicd_box.config(state=tk.NORMAL)
            elif file_path.endswith((".jpg", ".jpeg", ".png")):
                self.image = Image.open(file_path)
                self.chip_sicd_var.set(0)
                self.chip_sicd_box.config(state=tk.DISABLED)
            

            # Calculate initial zoom level to fit the entire image in the canvas
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            self.width, self.height = self.image.size

            # self.image_tk = ImageTk.PhotoImage(self.image.resize((int(self.width * self.imscale),
            #                                                     int(self.height * self.imscale))))
            self.imscale = 1.0  # scale for the canvaas image
            self.delta = 1.3  # zoom magnitude
            # Put image into container rectangle and use it to set proper coordinates to the image
            self.container = self.canvas.create_rectangle(0, 0, self.width, self.height, width=0)
            self.bbox = self.canvas.bbox(self.container)

            if self.image_id:
                self.canvas.delete(self.image_id)  # Remove previous image from canvas
            # self.image_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image_tk)
            # self.canvas.scale('all', 0, 0, zoom_level, zoom_level)  # rescale all canvas objects
            self.update_image()
            
            self.text_box.config(state=tk.NORMAL)
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert('1.0', f"{file_path}\n", "center")
            self.text_box.tag_configure("center", justify="center")

    def image_change(self, increment):
        if self.csv_box.get():
            self.export_csv()
        if self.pix_box.get():
            self.export_pix()
        if self.chip_png_var.get() or self.chip_sicd_var.get():
            self.chip()

        self.clear_rect()
        if self.current_image_index is not None:
            self.current_image_index = (self.current_image_index + increment)% len(self.image_paths)
            self.show_current_image()
            if self.bb_button.get():
                self.import_bounding_boxes()

    def next_image(self, event=None): 
        self.image_change(increment=1)
    def prev_image(self, event=None):
        self.image_change(increment=-1)
    
    def import_bounding_boxes(self):
        text_file_name = self.image_paths[self.current_image_index].replace(".png",".txt").replace(".ntf", ".txt")
        if text_file_name in [(self.directory + '/' + i) for i in os.listdir(self.directory)]:
            with open(text_file_name, "r") as f:
                lines = f.readlines()
            for templine in lines:
                line = templine.split(" ")
                print(line)
                if len(line)!=5:
                    print("bounding box file error")
                    return 
                coords = [(self.width*(float(line[1])-float(line[3])/2),
                        self.height*(float(line[2])-float(line[4])/2)),
                        (self.width*(float(line[1])+float(line[3])/2),
                        self.height*(float(line[2])+float(line[4])/2))]
                # self.image.rectangle(shape, outline ="red")
                self.rect = self.canvas.create_rectangle(coords[0][0], coords[0][1], coords[1][0], coords[1][1], fill="", outline="red")

                self.shapes.append(self.rect)
        else:
            print("No Bounding Box File Found")

    def remove_image(self):
        if not askyesno("File Deletion Warning","Are you sure you want to delete this file and any associated files?"):
            return

        if len(self.image_paths)==0:
            print("End of the line partner")
        elif len(self.image_paths)==1:
            deletion_file = self.image_paths[self.current_image_index]
            os.remove(deletion_file)
            deletion_txt = deletion_file[0:deletion_file.rfind('.')] + '.txt'
            if os.path.isfile(deletion_txt):
                os.remove(deletion_txt)
            deletion_file_pair = deletion_file.replace('static', 'moving')
            if os.path.isfile(deletion_file_pair):
                os.remove(deletion_file_pair)
            self.image_paths.pop(self.current_image_index)
        else:
            if self.csv_box.get():
                self.export_csv()
            if self.pix_box.get():
                self.export_pix()
            

            self.clear_rect()
            if self.current_image_index is not None:
                self.current_image_index = (self.current_image_index + 1)% len(self.image_paths)
                self.show_current_image()
                # print("h")

                if self.bb_button.get():

                    self.import_bounding_boxes()
            self.current_image_index-=1
            deletion_file = self.image_paths[self.current_image_index]
            os.remove(deletion_file)
            deletion_txt = deletion_file[0:deletion_file.rfind('.')] + '.txt'
            if os.path.isfile(deletion_txt):
                os.remove(deletion_txt)
            self.image_paths.pop(self.current_image_index)
        # self.image_paths[self.current_image_index]

    def on_button_press(self, event):
        # create rectangle if not yet exist
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.start_x = x
        self.start_y = y
        radio = self.radio.get()
        if radio <2:
            if radio == 0:
                self.rect = self.canvas.create_rectangle(x, y, x, y, fill="", outline="red")
                self.shapes.append(self.rect)
            elif radio ==1:
                self.line = self.canvas.create_line(x,y,x,y, fill='red', width=3)
                self.shapes.append(self.line)
            self.shape_type.append(radio)
        elif radio ==2 :
            ''' Remember previous coordinates for scrolling with the mouse '''
            self.canvas.scan_mark(event.x, event.y)

    def on_move_press(self, event):
        # expand rectangle as you drag the mouse
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        if self.radio.get() == 0:
            self.canvas.coords(self.rect, self.start_x, self.start_y, x, y)
        elif self.radio.get() ==1:
            self.canvas.coords(self.line, self.start_x, self.start_y, x, y)
        elif self.radio.get() ==2:
            ''' Drag (move) canvas to the new position '''
            self.canvas.scan_dragto(event.x, event.y, gain=1)
            self.update_image()  # redraw the image

    def move_from(self, event):
        ''' Remember previous coordinates for scrolling with the mouse '''
        self.canvas.scan_mark(event.x, event.y)

    def move_to(self, event):
        ''' Drag (move) canvas to the new position '''
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.show_image()  # redraw the image

    def on_button_release(self, event):
        # clear the rectangle
        self.rect_zoom = self.imscale
        self.rect = None
        self.line = None

    def right_click(self,event):
        if self.shapes:
            self.canvas.delete(self.shapes.pop())
    
    def middle_click(self, event):
        if self.radio.get()==0:
            self.radio.set(2)
        elif self.radio.get()==1:
            self.radio.set(0)
        elif self.radio.get()==2:
            self.radio.set(0)

    def clear_rect(self):
        while self.shapes:
            self.canvas.delete(self.shapes.pop())

    def export_pix(self):
        w, h = self.image.width, self.image.height
        vals = []
        for i, shape in enumerate(self.shapes):
            x1, y1, x2, y2 = self.get_shape_coords(shape)
            vals.append([(x1 +x2)/(2*w),(y1 +y2)/(2*h), abs(x1-x2)/(w),abs(y1 -y2)/(h)])
        output_file = self.image_paths[self.current_image_index].replace(".png",".txt").replace(".ntf",".txt")
        if len(vals) == 0:
            return 
        with open(output_file, "w") as f:
            # print(vals)
            for i in vals:
                f.write(f"{str(self.txt.get())} {str(i[0])} {str(i[1])} {str(i[2])} {str(i[3])}\n")


    def export_csv(self):
        columns = ['center', "corner0","corner1", "corner2", "corner3"]
        column_names = ["name"]
        column_names.extend([f"{column}_{xy}" for column in columns for xy in ['x', 'y']])
        # column_names.extend([f"{column}_{latlon}" for column in columns for latlon in ['lat', 'lon']])
        csv = os.path.join(self.directory,"bounding_box.csv")
        if os.path.isfile(csv):
            df = pd.read_csv(csv)
        else:
            df = pd.DataFrame(columns=column_names)
        for i, shape in enumerate(self.shapes):
            x1, y1,x2,y2 = self.get_shape_coords(shape)
            if self.shape_type[i] == 0:
                xy_arr = np.concatenate([[os.path.basename(self.image_paths[self.current_image_index])],
                                           [(x1+x2)/2, (y1+y2)/2, x1,y1, x2,y1, x2,y2, x1,y2]])
            else:
                xy_arr = np.concatenate([[os.path.basename(self.image_paths[self.current_image_index])],
                                           [(x1+x2)/2, (y1+y2)/2, x1,y1, x2,y2],
                                           [np.nan,np.nan, np.nan, np.nan]])
            df.loc[len(df)] = xy_arr
        df.drop_duplicates(keep='first', inplace=True)
        df.to_csv(csv, index=False)

def main():
    root = tk.Tk()
    root.state('zoomed')
    app = VisionLabelApp(root)
    app.open_image()

    # Set focus to the canvas after a short delay
    root.after(100, root.focus_force)
    root.mainloop()

if __name__ == "__main__":
    main()