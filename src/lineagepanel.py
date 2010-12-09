from experimentsettings import *
import wx
import numpy as np
from time import time
import icons
from wx.lib.combotreebox import ComboTreeBox


class LineageFrame(wx.Frame):
    def __init__(self, parent, id=-1, title='Experiment Lineage', **kwargs):
        wx.Frame.__init__(self, parent, id, title=title, **kwargs)
        
        sw = wx.ScrolledWindow(self)
        self.sw = sw
        timeline_panel = TimelinePanel(sw)
        self.timeline_panel = timeline_panel
        lineage_panel = LineagePanel(sw)
        self.lineage_panel = lineage_panel
        timeline_panel.set_style(padding=10)
        lineage_panel.set_style(padding=10, flask_gap = 40)
        sw.SetSizer(wx.BoxSizer(wx.VERTICAL))
        sw.Sizer.Add(timeline_panel, 0, wx.EXPAND|wx.LEFT, 40)
        sw.Sizer.Add(lineage_panel, 1, wx.EXPAND)
        sw.SetScrollbars(20, 20, self.Size[0]/20, self.Size[1]/20, 0, 0)
        sw.Fit()
        
        tb = self.CreateToolBar(wx.TB_HORZ_TEXT|wx.TB_FLAT)
        tb.AddControl(wx.StaticText(tb, -1, 'zoom'))
        self.zoom = tb.AddControl(wx.Slider(tb, -1, style=wx.SL_AUTOTICKS|wx.SL_LABELS)).GetControl()
        self.zoom.SetRange(1, 30)
        self.zoom.SetValue(8)
        x_spacing = tb.AddControl(wx.CheckBox(tb, -1, 'Time-relative branches'))
        x_spacing.GetControl().SetValue(0)
        generate = tb.AddControl(wx.Button(tb, -1, '+data'))        
        tb.Realize()
        
        #from f import TreeCtrlComboPopup
        #cc = wx.combo.ComboCtrl(sw)
        #self.tcp = TreeCtrlComboPopup()
        #cc.SetPopupControl(self.tcp)
        #sw.Sizer.Add(cc)
        #meta = ExperimentSettings.getInstance()        
        #meta.add_subscriber(self.on_metadata_changed, '')
        
        self.Bind(wx.EVT_SLIDER, self.on_zoom, self.zoom)
        self.Bind(wx.EVT_CHECKBOX, self.on_change_spacing, x_spacing)
        self.Bind(wx.EVT_BUTTON, self.generate_random_data, generate)
        
    def on_metadata_changed(self, tag):
        self.tcp.Clear()
        meta = ExperimentSettings.getInstance()
        alltags = meta.get_field_tags()
        t0 = set([tag.split('|')[0] for tag in alltags])
        for t in t0:
            item1 = self.tcp.AddItem(t)
            t1 = set([tag.split('|')[1] for tag in meta.get_field_tags(t)])
            for tt in t1:
                item2 = self.tcp.AddItem(tt, item1)
                t2 = set([tag.split('|')[2] for tag in meta.get_field_tags('%s|%s'%(t,tt))])
                for ttt in t2:
                    item3 = self.tcp.AddItem(ttt, item2)

        
    def on_zoom(self, evt):
        self.lineage_panel.set_style(node_radius=self.zoom.GetValue(),
                                     xgap=self.lineage_panel.NODE_R*2+1,
                                     ygap=self.lineage_panel.NODE_R*2+1)
        self.timeline_panel.set_style(icon_size=self.zoom.GetValue()*2,
                                      xgap=self.timeline_panel.ICON_SIZE+2)
        
    def on_change_spacing(self, evt):
        if evt.Checked():
            self.lineage_panel.set_time_x_spacing()
            self.timeline_panel.set_time_x_spacing()
        else:
            self.lineage_panel.set_even_x_spacing()
            self.timeline_panel.set_even_x_spacing()
    
    def generate_random_data(self, evt=None):
        meta = ExperimentSettings.getInstance()
        PlateDesign.add_plate('test', PLATE_TYPE)
        allwells = PlateDesign.get_well_ids(PlateDesign.get_plate_format('test'))
        event_types = ['AddProcess|Stain|Wells|0|',
                       'AddProcess|Wash|Wells|0|',
                       'AddProcess|Dry|Wells|0|',
                       'AddProcess|Spin|Wells|0|',
                       'Perturbation|Chem|Wells|0|',
                       'Perturbation|Bio|Wells|0|',
                       'DataAcquis|TLM|Wells|0|',
                       'DataAcquis|FCS|Wells|0|',
                       'DataAcquis|HCS|Wells|0|',
                       'CellTransfer|Seed|Wells|0|',
                       'CellTransfer|Harvest|Wells|0|']
        # GENERATE RANDOM EVENTS ON RANDOM WELLS
        for t in list(np.random.random_integers(0, MAX_TIMEPOINT, N_TIMEPOINTS)):
            for j in range(np.random.randint(1, N_FURCATIONS)):
                np.random.shuffle(allwells)
                well_ids = [('test', well) for well in allwells[:np.random.randint(1, len(allwells)+1)]]
                #timeline.add_event(t, 'event%d'%(t), well_ids)
                etype = event_types[np.random.randint(0,len(event_types))]
                meta.set_field('%s%s'%(etype, t), well_ids)


class TimelinePanel(wx.Panel):
    '''An interactive timeline panel
    '''
    # Drawing parameters
    PAD = 0.0
    ICON_SIZE = 16.0
    MIN_X_GAP = ICON_SIZE + 1
    TIC_SIZE = 2
    FONT_SIZE = (5,10)

    def __init__(self, parent, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)

        meta = ExperimentSettings.getInstance()
        meta.add_subscriber(self.on_timeline_updated, get_matchstring_for_subtag(2, 'Well'))
        self.timepoints = None
        self.events_by_timepoint = None
        self.cursor_pos = None
        self.hover_timepoint = None
        self.selection = None
        self.time_x = False
        
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_MOTION, self._on_mouse_motion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_mouse_exit)
        
    def set_style(self, padding=None, xgap=None, icon_size=None):
        if padding is not None:
            self.PAD = padding
        if xgap is not None:
            self.MIN_X_GAP = xgap
        if icon_size is not None:
            self.ICON_SIZE = icon_size
        self._recalculate_min_size()
        self.Refresh()
        self.Parent.FitInside()
        
    def set_time_x_spacing(self):
        self.time_x = True
        self._recalculate_min_size()
        self.Refresh()
        self.Parent.FitInside()

    def set_even_x_spacing(self):
        self.time_x = False
        self._recalculate_min_size()
        self.Refresh()
        self.Parent.FitInside()

    def on_timeline_updated(self, tag):
        meta = ExperimentSettings.getInstance()
        timeline = meta.get_timeline()
        self.events_by_timepoint = timeline.get_events_by_timepoint()
        self.timepoints = timeline.get_unique_timepoints()
        self._recalculate_min_size()
        self.Refresh()
        self.Parent.FitInside()
        
    def _recalculate_min_size(self):
        if self.timepoints is not None and len(self.timepoints) > 0:
            timeline = ExperimentSettings.getInstance().get_timeline()
            max_event_types_per_timepoint = \
                    max([len(set([get_tag_stump(evt.get_welltag()) for evt in evts]))
                         for t, evts in self.events_by_timepoint.items()])
            min_h = (max_event_types_per_timepoint+1) * self.ICON_SIZE + self.PAD * 2 + self.FONT_SIZE[1] + self.TIC_SIZE * 2 + 1
            if self.time_x:
                self.SetMinSize((self.PAD * 2 + self.MIN_X_GAP * self.timepoints[-1],
                                 min_h))
            else:
                self.SetMinSize((len(self.timepoints) * self.MIN_X_GAP + self.PAD * 2,
                                 min_h))

    def _on_paint(self, evt=None):
        '''Handler for paint events.
        '''
        if self.timepoints is None:
            return

        PAD = self.PAD + self.ICON_SIZE / 2.0
        ICON_SIZE = self.ICON_SIZE
        MIN_X_GAP = self.ICON_SIZE + 2
        TIC_SIZE = self.TIC_SIZE
        FONT_SIZE = self.FONT_SIZE
        MAX_TIMEPOINT = self.timepoints[-1]
        
        dc = wx.PaintDC(self)
        dc.Clear()
        dc.BeginDrawing()

        w_win, h_win = (float(self.Size[0]), float(self.Size[1]))
        if MAX_TIMEPOINT == 0:
            px_per_time = 1
        else:
            px_per_time = max((w_win - PAD * 2.0) / MAX_TIMEPOINT,
                              MIN_X_GAP)
        
        if len(self.timepoints) == 1:
            x_gap = 1
        else:
            x_gap = max(MIN_X_GAP, 
                         (w_win - PAD * 2) / (len(self.timepoints) - 1))

        # y pos of line
        y = h_win - PAD - FONT_SIZE[1] - TIC_SIZE - 1

        # draw the timeline
        if self.time_x:
            dc.DrawLine(PAD, y, 
                        px_per_time * MAX_TIMEPOINT + PAD, y)
        else:            
            dc.DrawLine(PAD, y, 
                        x_gap * (len(self.timepoints) - 1) + PAD, y)

        font = dc.Font
        font.SetPixelSize(FONT_SIZE)
        dc.SetFont(font)

        # draw event boxes
        for i, timepoint in enumerate(self.timepoints):
            # x position of timepoint on the line
            if self.time_x:
                x = timepoint * px_per_time + PAD
            else:
                x = i * x_gap + PAD
                
            if (self.cursor_pos is not None and 
                x-ICON_SIZE/2 < self.cursor_pos < x + ICON_SIZE/2):
                dc.SetPen(wx.Pen(wx.BLACK, 3))
                self.hover_timepoint = timepoint
            else:
                dc.SetPen(wx.Pen(wx.BLACK, 1))
                self.hover_timepoint = None
            # Draw tic marks
            dc.DrawLine(x, y - TIC_SIZE, 
                        x, y + TIC_SIZE)
            #dc.DrawRectangle(x, y, ICON_SIZE, ICON_SIZE)
            bmps = []
            process_types = set([])
            for i, ev in enumerate(self.events_by_timepoint[timepoint]):
                stump = get_tag_stump(ev.get_welltag())
                
                #for subtag in taxonomy.get_unique_instance_tag_stumps((0,1)):
                    #if stump.startswith(subtag) and stump not in process_types:
                        #bmps += [icons.__dict__[subtag].Scale(ICON_SIZE, ICON_SIZE, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()]
                
                if stump.startswith('CellTransfer|Seed') and stump not in process_types:
                    bmps += [icons.seed.Scale(ICON_SIZE, ICON_SIZE, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()]
                elif stump.startswith('CellTransfer|Harvest') and stump not in process_types:
                    bmps += [icons.harvest.Scale(ICON_SIZE, ICON_SIZE, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()]
                elif stump.startswith('Perturbation|Chem') and stump not in process_types:
                    bmps += [icons.treat.Scale(ICON_SIZE, ICON_SIZE, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()]
                elif stump.startswith('Perturbation|Bio') and stump not in process_types:
                    bmps += [icons.treat_bio.Scale(ICON_SIZE, ICON_SIZE, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()]
                elif stump.startswith('AddProcess|Stain') and stump not in process_types:
                    bmps += [icons.add_stain.Scale(ICON_SIZE, ICON_SIZE, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()]
                elif stump.startswith('AddProcess|Wash') and stump not in process_types:
                    bmps += [icons.wash.Scale(ICON_SIZE, ICON_SIZE, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()]
                elif stump.startswith('AddProcess|Dry') and stump not in process_types:
                    bmps += [icons.dry.Scale(ICON_SIZE, ICON_SIZE, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()]
                elif stump.startswith('AddProcess|Spin') and stump not in process_types:
                    bmps += [icons.spin.Scale(ICON_SIZE, ICON_SIZE, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()]
                elif stump.startswith('DataAcquis|HCS') and stump not in process_types:
                    bmps += [icons.imaging.Scale(ICON_SIZE, ICON_SIZE, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()]
                elif stump.startswith('DataAcquis|FCS') and stump not in process_types:
                    bmps += [icons.flow.Scale(ICON_SIZE, ICON_SIZE, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()]
                elif stump.startswith('DataAcquis|TLM') and stump not in process_types:
                    bmps += [icons.timelapse.Scale(ICON_SIZE, ICON_SIZE, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()]
                process_types.add(stump)
            for i, bmp in enumerate(bmps):
                dc.DrawBitmap(bmp, x - ICON_SIZE / 2.0, 
                              y - ((i+1)*ICON_SIZE) - TIC_SIZE - 1)
            wtext = FONT_SIZE[0] * len(str(timepoint))
            # draw the timepoint beneath the line
            dc.DrawText(str(timepoint), x - wtext/2.0, y + TIC_SIZE + 1)
        
        dc.EndDrawing()

    def _on_mouse_motion(self, evt):
        self.cursor_pos = evt.X
        self.Refresh()

    def _on_mouse_exit(self, evt):
        self.cursor_pos = None
        self.Refresh()
        
    def _on_click(self, evt):
        meta = ExperimentSettings.getInstance()
        timeline = meta.get_timeline()
        if self.hover_timepoint is not None:
            self.selection = (self.hover_timepoint, 
                              timeline.get_events_at_timepoint())


class LineagePanel(wx.Panel):
    '''A Panel that displays a lineage tree.
    '''
    # Drawing parameters
    PAD = 30
    NODE_R = 10
    MIN_X_GAP = NODE_R*2 + 2
    MIN_Y_GAP = NODE_R*2 + 2
    FLASK_GAP = MIN_X_GAP
    #X_SPACING = 'EVEN'

    def __init__(self, parent, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        self.nodes_by_timepoint = {}
        self.time_x = False
        self.cursor_pos = None
        
        meta = ExperimentSettings.getInstance()
        meta.add_subscriber(self.on_timeline_updated, 
                            get_matchstring_for_subtag(2, 'Well'))

        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_MOTION, self._on_mouse_motion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_mouse_exit)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_mouse_click)
        
    def set_time_x_spacing(self):
        self.time_x = True
        self._recalculate_min_size()
        self.Refresh()
        self.Parent.FitInside()

    def set_even_x_spacing(self):
        self.time_x = False
        self._recalculate_min_size()
        self.Refresh()
        self.Parent.FitInside()
        
    def set_style(self, padding=None, xgap=None, ygap=None, node_radius=None,
                  flask_gap=None):
        if padding is not None:
            self.PAD = padding
        if xgap is not None:
            self.MIN_X_GAP = xgap
        if ygap is not None:
            self.MIN_Y_GAP = ygap
        if node_radius is not None:
            self.NODE_R = node_radius
        if flask_gap is not None:
            self.FLASK_GAP = flask_gap
        self._recalculate_min_size()
        self.Refresh()
        self.Parent.FitInside()
     
    def on_timeline_updated(self, tag):
        '''called to add events to the timeline and update the lineage
        '''
        meta = ExperimentSettings.getInstance()
        timeline = meta.get_timeline()
        t0 = time()
        self.nodes_by_timepoint = timeline.get_nodes_by_timepoint()
        print 'built tree in %s seconds'%(time() - t0)
        self._recalculate_min_size()
        self.Refresh()
        self.Parent.FitInside()
        
    def _recalculate_min_size(self):
        meta = ExperimentSettings.getInstance()
        timepoints = meta.get_timeline().get_unique_timepoints()
        if len(timepoints) > 0:
            n_leaves = len(self.nodes_by_timepoint.get(timepoints[-1], []))
            if self.time_x:
                self.SetMinSize((self.PAD * 2 + self.MIN_X_GAP * timepoints[-1] + self.FLASK_GAP,
                                 n_leaves * self.MIN_Y_GAP + self.PAD * 2))
            else:
                self.SetMinSize((len(self.nodes_by_timepoint) * self.MIN_X_GAP + self.PAD * 2,
                                 n_leaves * self.MIN_Y_GAP + self.PAD * 2))

    def _on_paint(self, evt=None):
        '''Handler for paint events.
        '''
        if self.nodes_by_timepoint == {}:
            return

        t0 = time()
        PAD = self.PAD + self.NODE_R
        NODE_R = self.NODE_R
        MIN_X_GAP = self.MIN_X_GAP
        MIN_Y_GAP = self.MIN_Y_GAP
        FLASK_GAP = self.FLASK_GAP
        
        self.current_node = None

        meta = ExperimentSettings.getInstance()

        dc = wx.PaintDC(self)
        dc.Clear()
        dc.BeginDrawing()

        w_win, h_win = (float(self.Size[0]), float(self.Size[1]))

        # get the unique timpoints from the timeline
        timepoints = meta.get_timeline().get_unique_timepoints()
        timepoints.reverse()
        timepoints.append(-1)
        
        width = float(self.Size[0])
        height = float(self.Size[1])
        if len(self.nodes_by_timepoint) == 2:
            x_gap = 1
        else:
            # calculate the number of pixels to separate each generation timepoint
            x_gap = max(MIN_X_GAP, 
                         (width - PAD * 2 - FLASK_GAP) / (len(self.nodes_by_timepoint) - 2))
            
        if len(self.nodes_by_timepoint[timepoints[0]]) == 1:
            y_gap = MIN_Y_GAP
        else:
            # calcuate the minimum number of pixels to separate nodes on the y axis
            y_gap = max(MIN_Y_GAP, 
                        (height - PAD * 2) / (len(self.nodes_by_timepoint[timepoints[0]]) - 1))
            
        if timepoints[0] == 0:
            px_per_time = 1
        else:
            px_per_time = max((w_win - PAD * 2 - FLASK_GAP) / timepoints[0],
                              MIN_X_GAP)
            
        # Store y coords of children so we can calculate where to draw the parents
        nodeY = {}
        Y = PAD
        X = width - PAD
        dc.SetPen(wx.Pen("BLACK",1))

        # Iterate from leaf nodes up to the root, and draw R->L, Top->Bottom
        for i, t in enumerate(timepoints):
            #if i == len(timepoints) - 1:
                #pass
            if t == -1:
                X = PAD
            elif self.time_x:
                X = PAD + FLASK_GAP + t * px_per_time
                x_gap = PAD + FLASK_GAP + timepoints[i-1] * px_per_time - X
            else:
                X = PAD + FLASK_GAP + (len(timepoints) - i - 2) * x_gap
            
            if len(self.nodes_by_timepoint) == 1:
                X = width / 2
                Y = height / 2
                if (self.cursor_pos is not None and 
                    X-NODE_R < self.cursor_pos[0] < X + NODE_R and
                    Y-NODE_R < self.cursor_pos[1] < Y + NODE_R):
                    dc.SetBrush(wx.Brush('#FFFFAA'))
                    dc.SetPen(wx.Pen(wx.BLACK, 3))
                    self.current_node = self.nodes_by_timepoint.values()[0]
                else:
                    dc.SetBrush(wx.Brush('#FFFFFF'))
                    dc.SetPen(wx.Pen(wx.BLACK, 1))
                    self.current_node = None
                    
                dc.DrawCircle(X, Y, NODE_R)
                #dc.DrawText(str(self.nodes_by_timepoint[t][0].get_timepoint()), X, Y+NODE_R)
            elif i == 0:
                # Leaf nodes
                for node in self.nodes_by_timepoint[t]:
                    if (self.cursor_pos is not None and 
                        X-NODE_R < self.cursor_pos[0] < X + NODE_R and
                        Y-NODE_R < self.cursor_pos[1] < Y + NODE_R):
                        dc.SetBrush(wx.Brush('#FFFFAA'))
                        dc.SetPen(wx.Pen(wx.BLACK, 3))
                        self.current_node = node
                    else:
                        if len(node.get_tags()) > 0:
                            # If an event occurred
                            dc.SetBrush(wx.Brush('#333333'))
                        else:
                            # no event
                            dc.SetBrush(wx.Brush('#FFFFFF'))
                        dc.SetPen(wx.Pen(wx.BLACK, 1))
                    
                    dc.DrawCircle(X, Y, NODE_R)
                    #dc.DrawText(str(node.get_timepoint()), X, Y+NODE_R)
                    #if self.nodes_by_pos == {}:
                        #self.nodes_by_pos[(X,Y)] = node
                    nodeY[node.id] = Y
                    Y += y_gap
            else:
                # Internal nodes
                for node in self.nodes_by_timepoint[t]:
                    ys = []
                    for child in node.get_children():
                        ys.append(nodeY[child.id])
                    Y = (min(ys) + max(ys)) / 2

                    if (self.cursor_pos is not None and 
                        X-NODE_R < self.cursor_pos[0] < X + NODE_R and
                        Y-NODE_R < self.cursor_pos[1] < Y + NODE_R):
                        dc.SetBrush(wx.Brush('#FFFFAA'))
                        dc.SetPen(wx.Pen(wx.BLACK, 3))
                        self.current_node = node
                    else:
                        if len(node.get_tags()) > 0:
                            # If an event occurred
                            dc.SetBrush(wx.Brush('#333333'))
                        else:
                            # no event
                            dc.SetBrush(wx.Brush('#FFFFFF'))
                        dc.SetPen(wx.Pen(wx.BLACK, 1))
                    
                    if t == -1:
                        dc.DrawRectangle(X-NODE_R, Y-NODE_R, NODE_R*2, NODE_R*2)
                    else:
                        dc.DrawCircle(X, Y, NODE_R)
                    #dc.DrawText(str(node.get_timepoint()), X, Y+NODE_R)
                    #if self.nodes_by_pos == {}:
                        #self.nodes_by_pos[(X,Y)] = node
                        
                    dc.SetBrush(wx.Brush('#FFFFFF'))
                    dc.SetPen(wx.Pen(wx.BLACK, 1))

                    for child in node.get_children():
                        if t == -1:
                            dc.DrawLine(X + NODE_R, Y, 
                                        X + FLASK_GAP - NODE_R ,nodeY[child.id])
                        else:
                            dc.DrawLine(X + NODE_R, Y, 
                                        X + x_gap - NODE_R ,nodeY[child.id])
                    nodeY[node.id] = Y
        dc.EndDrawing()
        print 'rendered lineage in %.2f seconds'%(time() - t0)
        
    def _on_mouse_motion(self, evt):
        self.cursor_pos = (evt.X, evt.Y)
        self.Refresh()

    def _on_mouse_exit(self, evt):
        self.cursor_pos = None
        self.Refresh()

    def _on_mouse_click(self, evt):
        if self.current_node is None:
            return
        from properties import Properties
        import imagereader
        from imagetools import npToPIL
        Properties.getInstance().channels_per_image = '3'
        meta = ExperimentSettings.getInstance()
        for tag in (self.current_node.get_tags()):
            if (tag.startswith('DataAcquis|TLM') or 
                tag.startswith('DataAcquis|HCS')):
                for well in self.current_node.get_well_ids():
                    image_tag = '%s|Images|%s|%s|%s'%(get_tag_stump(tag, 2),
                                                      get_tag_instance(tag),
                                                      get_tag_timepoint(tag),
                                                      well)
                    urls = meta.get_field(image_tag, [])
                    for url in urls:
                        imdata = imagereader.ImageReader().ReadImages([url])
                        pil_image = npToPIL(imdata)
                        pil_image.show()
            elif tag.startswith('DataAcquis|FCS'):
                pass
                                               


        
if __name__ == "__main__":
    
    N_FURCATIONS = 2
    N_TIMEPOINTS = 5
    MAX_TIMEPOINT = 100
    PLATE_TYPE = P24
    
    app = wx.PySimpleApp()
    
    f = LineageFrame(None, size=(600, 300))
    f.Show()
    f.generate_random_data()

    #meta = ExperimentSettings.getInstance()
    #PlateDesign.add_plate('test', PLATE_TYPE)
    #allwells = PlateDesign.get_well_ids(PlateDesign.get_plate_format('test'))
    ## GENERATE RANDOM EVENTS ON RANDOM WELLS
    #for t in [0] + list(np.random.random_integers(1, MAX_TIMEPOINT, N_TIMEPOINTS)):
        #for j in range(np.random.randint(1, N_FURCATIONS)):
            #np.random.shuffle(allwells)
            #well_ids = [('test', well) for well in allwells[:np.random.randint(0, len(allwells))]]
            ##timeline.add_event(t, 'event%d'%(t), well_ids)
            #meta.set_field('AddProcess|Stain|Wells|0|%s'%(t), well_ids)
    
    app.MainLoop()

