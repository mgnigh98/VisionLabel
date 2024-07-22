import os
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import filedialog, scrolledtext
from PIL import Image, ImageTk
from sarpy.geometry import point_projection
from sarpy.io.complex.sicd import SICDReader
from sarpy.visualization.remap import Density

remap = Density()

class SICDViewerApp:
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

        button_frame = tk.Frame(top_frame)
        button_frame.pack(side=tk.LEFT)

        radio_frame = tk.Frame(top_frame)
        radio_frame.pack(side=tk.RIGHT)

        self.radio = tk.IntVar()
        self.r0 = tk.Radiobutton(radio_frame, text="Boxes", variable=self.radio, value=0)
        self.r0.pack(anchor= tk.W)
        self.r1 = tk.Radiobutton(radio_frame, text="Lines", variable=self.radio, value=1)
        self.r1.pack(anchor= tk.W)


        self.radio.set(0)



        # Create buttons for next and previous images
        self.prev_button = tk.Button(self.root, text="Prev", command=self.prev_image)
        self.prev_button.pack(side=tk.LEFT)
        self.next_button = tk.Button(self.root, text="Next", command=self.next_image)
        self.next_button.pack(side=tk.RIGHT)
        
        self.bb_button = tk.Button(self.root, text="Remove Image", command=self.remove_image)
        self.bb_button.pack(side=tk.TOP)

        self.latlon_box = tk.IntVar()
        self.pix_box = tk.IntVar()
        self.bb_button = tk.IntVar()
        self.export_latlon_box = tk.Checkbutton(button_frame, variable=self.latlon_box, text="Export Rectangles CSV", onvalue=1, offvalue=0)
        self.export_latlon_box.pack(side=tk.RIGHT)
        # self.export_latlon_button = tk.Button(self.button_frame, text="Export Rectangles LatLon", command=self.export_latlon)
        # self.export_latlon_button.pack(side=tk.RIGHT)
        self.export_pix_box = tk.Checkbutton(button_frame, variable=self.pix_box, text="Export Rectangles TXT", onvalue=1, offvalue=0)
        self.export_pix_box.pack(side=tk.LEFT)
        # self.export_pix_button = tk.Button(self.button_frame, text="Export Rectangles Pixels", command=self.export_pix)
        # self.export_pix_button.pack(side=tk.LEFT)
        self.import_bb_button = tk.Checkbutton(button_frame, variable=self.bb_button, text="Import Bounding Boxes", onvalue=1, offvalue=0, command=self.import_bounding_boxes)
        self.import_bb_button.pack(side=tk.TOP)
        # self.bb_button = tk.Checkbutton(self.root, text="Import Bounding Box", command=self.import_bounding_boxes)
        # self.bb_button.pack(side=tk.TOP)

        self.canvas = tk.Canvas(self.root, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=tk.YES)
        

        # Bind events for zooming and panning

        self.canvas.bind("<MouseWheel>", self.zoom)
        # self.root.bind('<Left>', self.pan_left)
        # self.root.bind('<Right>', self.pan_right)
        # self.root.bind('<Up>', self.pan_up)
        # self.root.bind('<Down>', self.pan_down)
        
        # Bind arrow keys for navigation
        self.root.bind("<Left>", self.prev_image)
        self.root.bind("<Right>", self.next_image)

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<ButtonPress-2>", self.middle_click)
        self.canvas.bind("<ButtonPress-3>", self.right_click)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        # Initial zoom level and pan offset
        self.zoom_level = 1.0
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
        
    def zoom(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        factor = 1.001**event.delta 
        self.canvas.scale(tk.ALL, x,y,factor,factor)
        self.zoom_level *= factor
        
        self.update_image()
        
    
    def update_image(self):
        if self.image:
            self.width = self.image.width * self.zoom_level
            self.height = self.image.height * self.zoom_level
            new_width = int(self.width)
            new_height = int(self.height)

            # Resize the image
            resized_image = self.image.resize((new_width, new_height), Image.LANCZOS)
            self.image_tk = ImageTk.PhotoImage(resized_image)

            # Update the image on canvas
            if self.image_id:
                self.canvas.itemconfig(self.image_id, image=self.image_tk)
                self.canvas.configure(scrollregion=(0, 0, new_width, new_height))
                self.canvas.xview_moveto(self.offset_x / new_width)
                self.canvas.yview_moveto(self.offset_y / new_height)


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
            elif file_path.endswith((".jpg", ".jpeg", ".png")):
                self.image = Image.open(file_path)
            

            # Calculate initial zoom level to fit the entire image in the canvas
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            image_width, image_height = self.image.size
            zoom_x = canvas_width / image_width
            zoom_y = canvas_height / image_height
            self.zoom_level = min(zoom_x, zoom_y)

            self.image_tk = ImageTk.PhotoImage(self.image.resize((int(image_width * self.zoom_level),
                                                                int(image_height * self.zoom_level))))
            if self.image_id:
                self.canvas.delete(self.image_id)  # Remove previous image from canvas
            self.image_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image_tk)
            self.update_image()
            
            self.text_box.config(state=tk.NORMAL)
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert('1.0', f"{file_path}\n", "center")
            self.text_box.tag_configure("center", justify="center")


    def next_image(self, event): 
        
        if self.latlon_box.get():
            self.export_latlon()
        if self.pix_box.get():
            self.export_pix()
        

        self.clear_rect()
        if self.current_image_index is not None:
            self.current_image_index = (self.current_image_index + 1)% len(self.image_paths)
            self.show_current_image()
            # print("h")

            print(self.bb_button.get())
            if self.bb_button.get():

                self.import_bounding_boxes()
    
    def import_bounding_boxes(self):
        text_file_name = self.image_paths[self.current_image_index].replace("png","txt")
        if text_file_name in [(self.directory + '/' + i) for i in os.listdir(self.directory)]:
            file = open(text_file_name, "r")
            line = file.readline().split(" ")
            if len(line)!=5:
                print("bounding box file error")
                return 
            coords = [(self.width*(float(line[1])-float(line[3])/2),
                    self.height*(float(line[2])-float(line[4])/2)),
                    (self.width*(float(line[1])+float(line[3])/2),
                    self.height*(float(line[2])+float(line[4])/2))]
            file.close()
            # self.image.rectangle(shape, outline ="red")
            self.rect = self.canvas.create_rectangle(coords[0][0], coords[0][1], coords[1][0], coords[1][1], fill="", outline="red")

            self.shapes.append(self.rect)
        else:
            print("No Bounding Box File Found")

    def remove_image(self):
        if len(self.image_paths)==0:
            print("End of the line partner")
        elif len(self.image_paths)==1:
            deletion_file = self.image_paths[self.current_image_index]
            os.remove(deletion_file)
            deletion_txt = deletion_file[0:deletion_file.rfind('.')] + '.txt'
            if os.path.isfile(deletion_txt):
                os.remove(deletion_txt)
            self.image_paths.pop(self.current_image_index)
        else:
            if self.latlon_box.get():
                self.export_latlon()
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

    def prev_image(self, event):
        if self.latlon_box.get():
            self.export_latlon()
        if self.pix_box.get():
            self.export_pix()
        

        self.clear_rect()
        if self.current_image_index is not None:
            self.current_image_index = (self.current_image_index - 1)% len(self.image_paths)
            self.show_current_image()
            if self.bb_button.get():
                self.import_bounding_boxes()

    def on_button_press(self, event):
        # create rectangle if not yet exist
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.start_x = x
        self.start_y = y
        radio = self.radio.get()
        if radio == 0:
            self.rect = self.canvas.create_rectangle(x, y, x, y, fill="", outline="red")
            self.shapes.append(self.rect)
        elif radio ==1:
            self.line = self.canvas.create_line(x,y,x,y, fill='red', width=3)
            self.shapes.append(self.line)
        self.shape_type.append(radio)

    def on_move_press(self, event):
        # expand rectangle as you drag the mouse
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        if self.radio.get() == 0:
            self.canvas.coords(self.rect, self.start_x, self.start_y, x, y)
        elif self.radio.get() ==1:
            self.canvas.coords(self.line, self.start_x, self.start_y, x, y)
        

    def on_button_release(self, event):
        # clear the rectangle
        self.rect_zoom = self.zoom_level
        self.rect = None
        self.line = None

    def right_click(self,event):
        if self.shapes:
            self.canvas.delete(self.shapes.pop())
    
    def middle_click(self, event):
        if self.radio.get()==1:
            self.radio.set(0)
        elif self.radio.get()==0:
            self.radio.set(1)


    def clear_rect(self):
        while self.shapes:
            self.canvas.delete(self.shapes.pop())

    def export_pix(self):
        #lat0,lon0 = self.sicd.sicd_meta.GeoData.ImageCorners.FRFC
        #lat,lon = self.sicd.sicd_meta.GeoData.ImageCorners.LRLC -self.sicd.sicd_meta.GeoData.ImageCorners.FRFC
        #print(self.sicd.sicd_meta.GeoData.ImageCorners.LRLC -self.sicd.sicd_meta.GeoData.ImageCorners.FRFC, self.sicd.sicd_meta.GeoData.ImageCorners.LRFC -self.sicd.sicd_meta.GeoData.ImageCorners.FRLC)
        #print(self.sicd.sicd_meta.GeoData.ImageCorners.FRFC,self.sicd.sicd_meta.GeoData.ImageCorners.FRLC,self.sicd.sicd_meta.GeoData.ImageCorners.LRLC,self.sicd.sicd_meta.GeoData.ImageCorners.LRFC)
        x, y = self.width, self.height
        w, h = self.image.width, self.image.height
        def xy_latlon(xy):
            # coords = point_projection.image_to_ground_geo(xy, self.sicd.sicd_meta, projection_type='PLANE')
            # return coords[:2]
            return xy[:2]
        columns = ['center', "corner0","corner1", "corner2", "corner3"]
        column_names = ["name"]
        column_names.extend([f"{column}_{latlon}" for column in columns for latlon in ['x', 'y']])
        # column_names.extend([f"{column}_{latlon}" for column in columns for latlon in ['lat', 'lon']])
        # csv = os.path.join(self.directory,"bounding_box_latlon.csv")
        # if os.path.isfile(csv):
        #     latlonDF = pd.read_csv(csv)
        # else:
        #     latlonDF = pd.DataFrame(columns=column_names)
        vals = []
        for i, shape in enumerate(self.shapes):
            # print(self.shape_type[i])
            x1, y1, x2, y2 = self.canvas.coords(shape)
            # print(x,y, w,h)
            # print([w*x1/x, h*y1/y],[w*x2/x, h*y2/y])
            # print(xy_latlon([w*x1/x, h*y1/y]),xy_latlon([w*x2/x, h*y2/y]))
            # print(xy_latlon([w*x1/x, h*y1/y]),xy_latlon([w*x2/x, h*y2/y]))

            vals.append([(w*x1/x +w*x2/x)/(2*w),(h*y1/y +h*y2/y)/(2*h), abs(w*x1/x-w*x2/x)/(w),abs(h*y1/y -h*y2/y)/(h)])
        output_file = self.image_paths[self.current_image_index].replace("png","txt")
        # print(output_file)
        if len(vals) == 0:
            return 
        file = open(output_file, "w")
        start = True

        for i in vals:
            if start:
                start = False
            else:
                file.write('\n')

            file.write(f"1 {str(i[0])} {str(i[1])} {str(i[2])} {str(i[3])}")

        file.close()



    def export_latlon(self):
        #lat0,lon0 = self.sicd.sicd_meta.GeoData.ImageCorners.FRFC
        #lat,lon = self.sicd.sicd_meta.GeoData.ImageCorners.LRLC -self.sicd.sicd_meta.GeoData.ImageCorners.FRFC
        #print(self.sicd.sicd_meta.GeoData.ImageCorners.LRLC -self.sicd.sicd_meta.GeoData.ImageCorners.FRFC, self.sicd.sicd_meta.GeoData.ImageCorners.LRFC -self.sicd.sicd_meta.GeoData.ImageCorners.FRLC)
        #print(self.sicd.sicd_meta.GeoData.ImageCorners.FRFC,self.sicd.sicd_meta.GeoData.ImageCorners.FRLC,self.sicd.sicd_meta.GeoData.ImageCorners.LRLC,self.sicd.sicd_meta.GeoData.ImageCorners.LRFC)
        x, y = self.width, self.height
        w, h = self.image.width, self.image.height
        def xy_latlon(xy):
            # coords = point_projection.image_to_ground_geo(xy, self.sicd.sicd_meta, projection_type='PLANE')
            # return coords[:2]
            return xy[:2]
        columns = ['center', "corner0","corner1", "corner2", "corner3"]
        column_names = ["name"]
        column_names.extend([f"{column}_{latlon}" for column in columns for latlon in ['x', 'y']])
        # column_names.extend([f"{column}_{latlon}" for column in columns for latlon in ['lat', 'lon']])
        csv = os.path.join(self.directory,"bounding_box_latlon.csv")
        if os.path.isfile(csv):
            latlonDF = pd.read_csv(csv)
        else:
            latlonDF = pd.DataFrame(columns=column_names)
        for i, shape in enumerate(self.shapes):
            # print(self.shape_type[i])
            x1, y1, x2, y2 = self.canvas.coords(shape)
            # print(x,y, w,h)
            # print([w*x1/x, h*y1/y],[w*x2/x, h*y2/y])
            # print(xy_latlon([w*x1/x, h*y1/y]),xy_latlon([w*x2/x, h*y2/y]))
            if self.shape_type[i] == 0:
                latlon_arr = np.concatenate([[os.path.basename(self.image_paths[self.current_image_index])],
                                           xy_latlon([w/x*(x1+x2)/2, h/y*(y1+y2)/2]),
                                           xy_latlon([w*x1/x, h*y1/y]),xy_latlon([w*x2/x, h*y1/y]),
                                           xy_latlon([w*x2/x, h*y2/y]),xy_latlon([w*x1/x, h*y2/y])])
            else:
                latlon_arr = np.concatenate([[os.path.basename(self.image_paths[self.current_image_index])],
                                           xy_latlon([w/x*(x1+x2)/2, h/y*(y1+y2)/2]),
                                           xy_latlon([w*x1/x, h*y1/y]),xy_latlon([w*x2/x, h*y2/y]),
                                           [np.nan,np.nan, np.nan, np.nan]])
            latlonDF.loc[len(latlonDF)] = latlon_arr
        latlonDF.drop_duplicates(keep='first', inplace=True)
        latlonDF.to_csv(csv, index=False)



def main():
    root = tk.Tk()
    root.state('zoomed')
    app = SICDViewerApp(root)
    app.open_image()

    # Set focus to the canvas after a short delay
    root.after(100, root.focus_force)
    root.mainloop()

if __name__ == "__main__":
    main()