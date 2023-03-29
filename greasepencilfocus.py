bl_info = {
    "name": "Grease Pencil Focus",
    "description": "automated tasks and shortcuts for the Greasepencil tool",
    "author": "Dédouze / andry@dedouze.com",
    "version": (1, 3, 4),
    "blender": (3, 1, 2),
    "location": "'Ctrl + Shift + F' is the default shortcut",
    "warning": "",
    "doc_url": "https://github.com/dedouze/greasepencilfocus",
    "tracker_url": "https://github.com/dedouze/greasepencilfocus",
    "category": "Object",
    "support": "COMMUNITY",
    }

#****************** TODO / BUGS
# - Move code to clean folder/files system
# - Optimize the multiple call of listeners
# - retrieve data when layers are renamed, and delete data from old layer names
# - add more layer actions in the popup


import os
import bpy
from bpy.props import *
from bpy.types import AddonPreferences
from bl_ui import space_toolsystem_common
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, StringProperty, IntProperty
from bpy.types import PropertyGroup, UIList, Operator
import time

# Global list to store the last 5 selected Grease Pencil objects
active_gp_objects_history = []

class GREASEPENCILFOCUS_Props(PropertyGroup):
    addon_tab: EnumProperty(
        name="COLLECTION",
        description="",
        items=[
            ('ACTIVE_OBJECT', "Current", ""),
            ('GP_OBJECTS', "Recent", "")
        ],
        default='ACTIVE_OBJECT')
        
    tool_tab: EnumProperty(
        name="TOOLS",
        description="",
        items=[
            ('LAYERS', "Layers", "View Layer"),
            ('MATERIALS', "Materials", "Add Material"),
            ('ADD_LAYER', "Add Layer", "Add Layer")
        ],
        default='LAYERS')
    force_draw_mode: bpy.props.BoolProperty(name='Force draw mode when switching to object', default=True)
    save_view_on_object: bpy.props.BoolProperty(name='Save last view or camera position for each object', default=False)
    auto_switch_tools: bpy.props.BoolProperty(name='Save and reactivate tool settings for each layer', default=True)
    add_layer_name:  bpy.props.StringProperty(name='Layer Name', subtype = "NONE", default='Layer')
    add_layer_position: EnumProperty(
        name="Position",
        description="",
        items=[
            ('OVER', "Over current layer", ""),
            ('BELOW', "Below current layer", "")
        ],
        default='OVER')
    
    add_mat_name: bpy.props.StringProperty(name='Material Name', subtype = "NONE", default='Material')
    add_mat_show_stroke: bpy.props.BoolProperty(name='Show Stroke', default=True)
    add_mat_stroke_color: bpy.props.FloatVectorProperty(
        name = "Stroke Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (0.0,0.2,0.7,1.0))
    
    add_mat_show_fill: bpy.props.BoolProperty(name='Show Fill', default=False)
    add_mat_fill_color: bpy.props.FloatVectorProperty(
        name = "Fill Color",
        subtype = "COLOR",
        size = 4,
        min = 0.0,
        max = 1.0,
        default = (1.0,1.0,0.3,1.0))

def get_addon_preferences():
    addon_name = os.path.splitext(__name__)[0]
    addon_prefs = bpy.context.preferences.addons[addon_name].preferences
    return (addon_prefs)

def obj_selected_callback(*args):
    log("object selected!")

    load_object_gp_settings()
    init_active_object_listeners()

def load_object_view_settings():
    if not is_in_viewport() or is_animation_playing():
        return
    
    if bpy.context.active_object.get('last_view_settings') is not None:
        view3d = bpy.context.space_data
        region3d = view3d.region_3d

        values = bpy.context.active_object['last_view_settings']

        region3d.view_distance = values['view_distance']
        region3d.view_location = values['view_location']
        region3d.view_rotation = values['view_rotation']
        region3d.view_perspective = values['view_perspective']
        view3d.lens = values['lens']

def load_object_gp_settings():

    props = bpy.context.scene.greasepencilfocus
    if not props.auto_switch_tools:
        return

    if not bpy.context.active_object or bpy.context.active_object.type != "GPENCIL":
        return

    update_active_gp_objects_history(bpy.context.active_object)

    log("load gp settings for object " + bpy.context.active_object.name + ":")

    stroke_placement_key = "gpencil_stroke_placement_view3d"
    lock_axis_key = "gpencil_sculpt_lock_axis"
    if stroke_placement_key in bpy.context.active_object and bpy.context.active_object[stroke_placement_key] != bpy.context.scene.tool_settings.gpencil_stroke_placement_view3d:
        bpy.context.scene.tool_settings.gpencil_stroke_placement_view3d = bpy.context.active_object[stroke_placement_key]

    if lock_axis_key in bpy.context.active_object and bpy.context.active_object[lock_axis_key] != bpy.context.scene.tool_settings.gpencil_stroke_placement_view3d:
        bpy.context.scene.tool_settings.gpencil_sculpt.lock_axis = bpy.context.active_object[lock_axis_key]

def get_area_space():
    
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            if area.spaces[0] is not None:
                return area.spaces[0]
    return None

def is_in_viewport():
    return (
        bpy.context.space_data is not None
        and bpy.context.space_data.type == 'VIEW_3D'
    )

def is_animation_playing():
    return (
        bpy.context.screen is None 
        or bpy.context.screen.is_animation_playing
    )

def init_viewport_handlers(): 
    bpy.context.scene['view_last_saved_time'] = time.time()
    
    areaSpace = get_area_space()
    if areaSpace is not None:
        log('init viewport handlers')
        args = (areaSpace, object())
        areaSpace.draw_handler_add(view_updated_callback, args, 'WINDOW', 'POST_PIXEL')

def view_updated_callback(rv3d, arg1):
    if is_animation_playing():
        return

    now_time = time.time()
    
    # wait 1 second before next call for optimization
    if bpy.context.scene.get('view_last_saved_time') is not None and now_time - bpy.context.scene['view_last_saved_time'] < 1:
        return

    view3d = bpy.context.space_data
    region3d = view3d.region_3d

    bpy.context.scene['view_last_saved_time'] = now_time

    if bpy.context.active_object:

        log('view changed for object')

        bpy.context.active_object['last_view_settings'] = {
            'view_distance': region3d.view_distance,
            # 'view_camera_zoom': region3d.view_camera_zoom,
            # 'view_camera_offset': rv3d.view_camera_offset,
            # 'is_perspective': region3d.is_perspective,
            'view_perspective': region3d.view_perspective,
            'view_location': region3d.view_location,
            # 'view_matrix': region3d.view_matrix,
            'view_rotation': region3d.view_rotation,
            'lens': view3d.lens
        } 
     

#    subscribe_to = rv3d, "view_rotation"

#    bpy.msgbus.subscribe_rna(
#        key=subscribe_to,
#        owner=bpy.types.Scene,
#        args=(),
#        notify=view_changed_callback)

def generateStoreKeyByLayerName(name):
    return "layer-" + name + "-preferences"

def loadLayerPreferences(object, layerName):
    globalKey = 'gpfocus_layer_preferences'
    if object.get(globalKey) is None:
        return None
    if layerName in object[globalKey]:
        return object[globalKey][layerName]
    return None

def saveLayerPreferences(object, layerName, values):
    globalKey = 'gpfocus_layer_preferences'
    if object.get(globalKey) is None:
        object[globalKey] = {}

    object[globalKey][layerName] = values
    
    log("<<<< Saved to layer ID " + layerName)
    log(values)


def layer_selected_callback():
    log("layer selected " + bpy.context.active_object.data.layers.active.info)
    
    props = bpy.context.scene.greasepencilfocus
    if not props.auto_switch_tools:
        return

    values = loadLayerPreferences(bpy.context.active_object, bpy.context.active_object.data.layers.active.info)
    if values is not None:
        brushName = values["brush_name"]
        brushSize = values["brush_size"]
        materialIndex = values["active_material_index"]

        log(">>>> saved preferences found :) " + brushName)

        if bpy.context.scene.tool_settings.gpencil_paint.brush != bpy.data.brushes[brushName]:
            bpy.context.scene.tool_settings.gpencil_paint.brush = bpy.data.brushes[brushName]

        if bpy.context.scene.tool_settings.gpencil_paint.brush.size != brushSize:
            bpy.context.scene.tool_settings.gpencil_paint.brush.size = brushSize

        if bpy.context.active_object.active_material_index != materialIndex:
            bpy.context.active_object.active_material_index = materialIndex
    else:
        log(">>!! no saved settings. Saving current settings in layer " + bpy.context.active_object.data.layers.active.info)
        save_last_tool()
        
    tools = bpy.context.workspace.tools 
    current_active_tool = tools.from_space_view3d_mode(bpy.context.mode).idname
    log(current_active_tool)


def update_active_gp_objects_history(obj):
    global active_gp_objects_history
    
    if obj.type == 'GPENCIL':
        if obj not in active_gp_objects_history:
            active_gp_objects_history.insert(0, obj)
        else:
            active_gp_objects_history.remove(obj)
            active_gp_objects_history.insert(0, obj)

    preferences = get_addon_preferences()
        
    if len(active_gp_objects_history) > preferences.objects_history_length:
        del active_gp_objects_history[-1]

class clickInGpHistoryOperator(bpy.types.Operator):
    bl_idname = "object.click_in_gp_objects_history"
    bl_label = "Select Grease Pencil Object"
    bl_options = {'REGISTER', 'UNDO'}
    object_name: bpy.props.StringProperty(name="Grease Pencil Object")
    
    def execute(self, context):
        scene = context.scene

        # Change to object mode before selecting another object
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        object_name = self.properties.object_name if hasattr(self.properties, "object_name") else self.object_name
        obj = bpy.data.objects[object_name]
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj

        # Switch to draw mode if "force_draw_mode" is enabled
        if scene.gpencil_force_draw_mode:
            bpy.ops.object.mode_set(mode='PAINT_GPENCIL')
        
        return {'FINISHED'}
    
def workspace_tools_rna_callback(workspace):
    idname = workspace.tools[-1].idname
    log("tool selected " + idname)
    save_last_tool()

def subscribe_workspace_tools(workspace):
    bpy.msgbus.subscribe_rna(
        key=workspace.path_resolve("tools", False),
        owner=workspace,
        args=(workspace,),
        notify=workspace_tools_rna_callback)
        
        
# Listen to material change

def init_active_object_listeners():
    if bpy.context.active_object is None:
        return
        l
    log("init listeners? ")
    
    if not bpy.context.active_object or bpy.context.active_object.type != "GPENCIL":
        return
    
    if "materials_listener_already_inited" in bpy.context.active_object and bpy.context.active_object["materials_listener_already_inited"] == 1:
        return

    log("init adding listeners OK ")
    
    bpy.context.active_object["materials_listener_already_inited"] = 1
    
    def mat_rna_callback():
        log("material selected " + bpy.context.active_object.active_material.name)
        bpy.data.brushes
        save_last_tool()

    subscribe_to_mat = bpy.context.active_object.path_resolve("active_material_index", False)
    
    subscribe_owner = bpy.types.Scene.greasepencilfocus

    bpy.msgbus.subscribe_rna(
        key=subscribe_to_mat,
        owner=subscribe_owner,
        args=(),
        notify=mat_rna_callback)
        
    save_last_tool()
 
# Listen to brush change    

def brush_rna_callback():
    log("brush selected " + bpy.context.scene.tool_settings.gpencil_paint.brush.name)
    save_last_tool()

def stroke_placement_and_axis_rna_callback():
    if not bpy.context.active_object or bpy.context.active_object.type != "GPENCIL":
        return

    log("saving stroke placement in " + bpy.context.active_object.name + " :")
    
    stroke_placement = bpy.context.scene.tool_settings.gpencil_stroke_placement_view3d
    lock_axis = bpy.context.scene.tool_settings.gpencil_sculpt.lock_axis

    bpy.context.active_object["gpencil_stroke_placement_view3d"] = stroke_placement
    bpy.context.active_object["gpencil_sculpt_lock_axis"] = lock_axis
    
def save_last_tool():
    
    props = bpy.context.scene.greasepencilfocus
    if not props.auto_switch_tools:
        return

    if not bpy.context.active_object or  bpy.context.active_object.type != "GPENCIL":
        return
    
    # Save only the brushes that are not in the erasers lists
    if 'Eraser' not in bpy.context.scene.tool_settings.gpencil_paint.brush.name:
        saveLayerPreferences(bpy.context.active_object, bpy.context.active_object.data.layers.active.info, {
            "brush_name": bpy.context.scene.tool_settings.gpencil_paint.brush.name,
            "brush_size": bpy.context.scene.tool_settings.gpencil_paint.brush.size,
            "active_material_index": bpy.context.active_object.active_material_index
        })

#bpy.types.GPencilFrame
# .BrushGpencilSettings

#************ PANEL MODE TEST


class ExamplePanel(bpy.types.Panel):
    
    bl_idname = 'GP_FOCUS_PANEL'
    bl_label = 'Example Panel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    
    def draw(self, context):
        _draw_layers(self, self.layout, context)

#************ MODAL

class LaunchModal(bpy.types.Operator):
    bl_label = "Focus Popup"
    bl_idname = "greasepencil.focuspopup"
    bl_options = {'REGISTER', 'UNDO'}


    def invoke(self, context, event):
		# addon_prefs = preference()
        # 
        
        preferences = get_addon_preferences()
        
        # return context.window_manager.invoke_props_dialog(self, width=preferences.popup_width)
        return context.window_manager.invoke_popup(self, width=preferences.popup_width)
    
    def draw(self, context):
        #_draw_layers(self, self.layout, context)
        panel_main_menu(self, context)

    def execute(self, context):
        return {'RUNNING_MODAL'}
        # return {'FINISHED'}

# store keymaps here to access after registration
addon_keymaps = []

@persistent
def on_reload(dummy):
    init_handlers()
    bpy.app.handlers.depsgraph_update_post.append(active_layer_switch_handler)
    
def active_layer_switch_handler(scene):
    # Access the active object
    active_object = bpy.context.active_object

    # Check if the active object is a grease pencil object
    if active_object and active_object.type == 'GPENCIL':
        # Access the grease pencil data
        gpencil_data = active_object.data

        # Access the active grease pencil layer
        active_layer = gpencil_data.layers.active

        # Check if the active layer has changed
        if active_object.get("active_gpencil_layer") != active_layer.info:
            # Update the active layer information
            active_object["active_gpencil_layer"] = active_layer.info

            # Do something with the active grease pencil layer
            print("Active Grease Pencil Layer switched to:", active_layer.info)
            layer_selected_callback()


def init_handlers():    
    
    bpy.types.Scene.greasepencilfocus = PointerProperty(type=GREASEPENCILFOCUS_Props)
    subscribe_owner = bpy.types.Scene.greasepencilfocus # apparently any python object can be owner ??

    ############# SUBSCRIBE TO OBJECT SWITCH
    subscribe_to = bpy.types.LayerObjects, "active"
    bpy.msgbus.subscribe_rna(
        key=subscribe_to,
        owner=subscribe_owner,
        args=(),
        notify=obj_selected_callback
    )

    ############# SUBSCRIBE TO GP BRUSH TYPE SWITCH
    log("GP focus addon init_handlers")
    subscribe_to_brush = bpy.context.scene.tool_settings.gpencil_paint

    bpy.msgbus.subscribe_rna(
        key=subscribe_to_brush,
        owner=subscribe_owner,
        args=(),
        notify=brush_rna_callback
    )
    
    ############# SUBSCRIBE TO GP BRUSH SIZE CHANGE
    subscribe_to_brush_size = bpy.context.scene.tool_settings.gpencil_paint.brush

    bpy.msgbus.subscribe_rna(
        key=subscribe_to_brush_size,
        owner=subscribe_owner,
        args=(),
        notify=brush_rna_callback
    )
            
    ############# SUBSCRIBE TO GP STROKE PLACEMENT SWITCH 

    subscribe_to_stroke_placement = bpy.types.ToolSettings, "gpencil_stroke_placement_view3d"

    bpy.msgbus.subscribe_rna(
        key=subscribe_to_stroke_placement,
        owner=subscribe_owner,
        args=(),
        notify=stroke_placement_and_axis_rna_callback)  
        
        
    subscribe_to_stroke_axis = bpy.types.GPencilSculptSettings, "lock_axis"

    bpy.msgbus.subscribe_rna(
        key=subscribe_to_stroke_axis,
        owner=subscribe_owner,
        args=(),
        notify=stroke_placement_and_axis_rna_callback)  

    ############# SUBSCRIBE TO WORKSPACE EVENTS

    for ws in bpy.data.workspaces:
        log("adding workspace " + ws.name)
        subscribe_workspace_tools(ws)
    #subscribe(bpy.context.workspace)
    
    ############ RESET THE SECURITY LOCK FOR RE-SUBSCRIPTION ON MATERIALS
    for obj in bpy.context.scene.objects:
        if obj.type == "GPENCIL":
            obj["materials_listener_already_inited"] = 0

    ############# LISTEN TO VIEWPORT UPDATES FOR CAMERA VIEW 
    init_viewport_handlers()

    ############# Object listener
    init_active_object_listeners()
    

    # Add "force_draw_mode" property to the scene
    bpy.types.Scene.gpencil_force_draw_mode = bpy.props.BoolProperty(
        name="Force Draw Mode",
        description="Automatically switch to draw mode when selecting an object from the history list",
        default=True
    )

    populate_gp_objects_history()

def init_context():
    init_handlers()
    register_keymaps()

def register_keymaps():
    wm = bpy.context.window_manager
    preferences = get_addon_preferences()
    
    kc = wm.keyconfigs.addon
    if kc:
        km = wm.keyconfigs.addon.keymaps.new(name='Grease Pencil', space_type='EMPTY', region_type='WINDOW')
        kmi = km.keymap_items.new(
            LaunchModal.bl_idname,
            preferences.key_shortcut,
            value="PRESS",
            alt=preferences.use_alt,
            ctrl=preferences.use_ctrl,
            shift=preferences.use_shift
        )
        
        addon_keymaps.append((km, kmi))

def unregister_keymaps():
    # handle the keymap
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

def refresh_preferences(self, context):
    unregister_keymaps()
    register_keymaps()

def log(value):
    preferences = get_addon_preferences()
    if preferences.debug_mode:
        print(value)

class GreasePencilFocusAddonPreferences(AddonPreferences):
    bl_idname = os.path.splitext(__name__)[0]
    
    key_shortcut: StringProperty(
        name = "Key Shortcut",
        subtype = "NONE",
        default = "F",
        update = refresh_preferences
    )

    debug_mode: BoolProperty(
        name = "Debug Mode",
        default = False
    )
    
    key_shortcut: StringProperty(
        name = "Key Shortcut",
        subtype = "NONE",
        default = "F",
        update = refresh_preferences
    )
    use_shift: BoolProperty(
        name = "combine with shift",
        description = "add shift",
        default = True,
        update = refresh_preferences
    )

    use_alt: BoolProperty(
        name = "combine with alt",
        description = "add alt",
        default = False,
        update = refresh_preferences
    )

    use_ctrl: BoolProperty(
        name = "combine with ctrl",
        description = "add ctrl",
        default = True,
        update = refresh_preferences
    )

    popup_width: IntProperty(
        name = "Popup width",
        subtype = "NONE",
        default = 300,
        update = refresh_preferences
    )

    objects_history_length: IntProperty(
        name = "Objects history length",
        subtype = "NONE",
        default = 5,
        update = refresh_preferences,
        min = 2,
        max = 100
    )

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        row = col.row()
        row.prop(self, "key_shortcut")
        col.separator()

        row = col.row()

        row.prop(self, "use_shift")
        row.prop(self, "use_alt")
        row.prop(self, "use_ctrl")
        col.separator()

        row = col.row()
        row.alignment ="RIGHT"
        row.prop(self, "popup_width")
        row.prop(self, "objects_history_length")
        row.prop(self, "debug_mode")

# ****************** NEW PANELS

def panel_main_menu(self, context):
    
    props = bpy.context.scene.greasepencilfocus

    self.layout.prop(props,"addon_tab", expand=True)

    #######################################
    if props.addon_tab == "ACTIVE_OBJECT":
        #######################################

        # layout.prop(addon_prefs,"tool_tab", expand=True)
        if props.tool_tab == "LAYERS":
            _draw_layers(self, self.layout, context)
        elif props.tool_tab == "MATERIALS":
            _draw_materials(self, self.layout, context)
        elif props.tool_tab == "ADD_LAYER":
            _draw_add_layer(self, self.layout, context)

    elif props.addon_tab == 'GP_OBJECTS':

        # layout.use_property_split = False
        # view_layer = context.view_layer
        
        _draw_gp_objects(self, self.layout, context)

def collection_manager_menu(self, context, layout):
	cm = context.scene.collection_manager
	layout.row().template_list("CM_UL_items", "",
							   cm, "cm_list_collection",
							   cm, "cm_list_index",
							   rows=15,
							   sort_lock=True)
# def listLayerCollection(layerCollections, col):
#     count_gp_obj = 0
#     for item in layerCollections:
#         if not item.is_visible:
#             continue
#         collection = item.collection
#         row = col.row(align=True)
#         row.label(text=collection.name,icon="OUTLINER_COLLECTION")
#         row.active = False

#         for object in collection.all_objects:
#             if object.type != 'GPENCIL':
#                 continue
#             if object.name not in bpy.context.view_layer.objects:
#                 # what is this case? object not in view_layer ??
#                 continue
            
#             count_gp_obj += 1
#             row = col.row(align=True)

#             # row_l = row.split(align=True,factor=1)
#             # row_l.label(text=object.name,icon="NONE")
            
#             row_i = row.row(align=True)
#             row_i.operator(SwitchToObjectOperator.bl_idname, text=object.name, icon="OUTLINER_OB_GREASEPENCIL", emboss=False).object_name = object.name
            
            
#             row_i.operator(SwitchObjectVisibility.bl_idname, icon= "HIDE_ON" if object.hide_get() else "HIDE_OFF", emboss=False, text="").object_name = object.name
            
#             row_i.prop(object, "hide_render", icon='RESTRICT_RENDER_OFF', emboss=False, text="")
#             row_i.active = (bpy.context.active_object == object)

        
#         # no need to loop in children collection, already visible in previous list !

#         # if item.children:
#         #     listLayerCollection(item.children, col)
#     if count_gp_obj == 0:
#         col.separator()
#         row = col.row(align=True)
#         row.label(text="You don't have any visible Greasepencil object")
#         row.active = False

                
def _draw_gp_objects(self, layout, context):
    global active_gp_objects_history

    props = context.scene.greasepencilfocus

    col = layout.column(align=True)
    log("list GP objects")

    box = layout.box()
    col = box.column(align=True)

    col.label(text="Most recently used Grease Pencil Objects:")
    
    if bpy.data.objects: # do nothing if the scene is empty
        for obj in active_gp_objects_history:
            if obj is not None and obj.name and (obj.name in bpy.data.objects):  # Check if the object still exists and was not deleted
                selectable = obj in context.view_layer.objects.values()  # Check if the object is selectable in the current View Layer
                if selectable:
                    op = col.operator("object.click_in_gp_objects_history", text=obj.name).object_name = obj.name
                else:
                    # op = col.operator("object.click_in_gp_objects_history", text=obj.name, emboss=False,icon='UNLINKED').object_name = obj.name  # Draw the operator with greyed out text and an icon indicating it's not selectable
                    # op.enabled = False
                    #the enabled false is not working, let's just remove the object
                    active_gp_objects_history.remove(obj)  # Remove the object from the list if it doesn't exist
            else:
                active_gp_objects_history.remove(obj)  # Remove the object from the list if it doesn't exist

    # Draw "Force Draw Mode" checkbox
    scene = context.scene
    layout.prop(scene, "gpencil_force_draw_mode")
        
class ColorItem(bpy.types.PropertyGroup):
    color = bpy.props.FloatVectorProperty(
                 name = "Color Picker",
                 subtype = "COLOR",
                 size = 4,
                 min = 0.0,
                 max = 1.0,
                 default = (1.0,1.0,1.0,1.0)
                 )
    
def populate_gp_objects_history():
    log('populate_gp_objects_history')
    global active_gp_objects_history

    #in case we load a new scene (after load_post), empty the history
    active_gp_objects_history.clear()
    
    context = bpy.context
    objects = context.scene.objects
    active_obj = context.view_layer.objects.active
    
    # Pre-populate history list with first 5 Grease Pencil objects in the scene
    grease_pencil_objects = [obj for obj in objects if obj.type == 'GPENCIL']
    active_gp_objects_history.extend(grease_pencil_objects[:5])
    
    # Move active Grease Pencil object to the beginning of the list
    if active_obj and active_obj.type == 'GPENCIL':
        update_active_gp_objects_history(active_obj)
        log('object already active added')

def _draw_materials(self, layout, context):
    
    addon_prefs = get_addon_preferences()
    #row = layout.row()

    # row.prop(context.scene, "mytool_color")
    #row.prop(colors[0], "color", text='Pick Color')

    # log("draw layers, active index ")

    col = layout.column()

    row = col.row()
    row.label(text= "Add Material :")
    col.separator()

    props = context.scene.greasepencilfocus

    # for (prop_name, _) in props:
    #     row = col.row()
    #     row.prop(context.scene, prop_name)

    row = col.row()
    row.prop(props, 'add_mat_name', text="Material")

    row = col.row()
    row.prop(props, 'add_mat_show_stroke', text="Stroke")
    row.prop(props, 'add_mat_stroke_color', text="")
    
    row = col.row()
    row.prop(props, 'add_mat_show_fill', text="Fill")
    row.prop(props, 'add_mat_fill_color', text="")

    # col.operator(bpy.ops.ui.eyedropper_color.idname(), text="pick color")

    col.separator()
    col.operator(AddMaterialOperator.bl_idname, text='Add')
    col.separator()

    row = col.row(align=True)
    row_s = row.row(align=True)
    row_s_obj = row_s.operator(SwitchToSubTabOperator.bl_idname,text="Back to layers",icon="RIGHTARROW_THIN",emboss=False)
    row_s_obj.tab_name = "LAYERS"
    row.separator()

def _draw_add_layer(self, layout, context):
    
    props = context.scene.greasepencilfocus

    col = layout.column()

    row = col.row()
    row.label(text= "Add Layer")
    col.separator()

    row = col.row()
    row.prop(props, 'add_layer_name', text="Name")
    col.separator()

    row = col.row()
    row.prop(props,"add_layer_position")
    col.separator()

    row = col.row()
    row.operator(AddLayerOperator.bl_idname, text="Add")

    col.separator()

    row = col.row(align=True)
    row_s = row.row(align=True)
    row_s_obj = row_s.operator(SwitchToSubTabOperator.bl_idname,text="Back to layers",icon="RIGHTARROW_THIN",emboss=False)
    row_s_obj.tab_name = "LAYERS"
    row.separator()

        

class LAYERS_UL_items(UIList):
    def __init__(self):
        self.use_filter_sort_reverse = True
    
    def draw_filter(self, context, layout):
        layout.separator()

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # is_debug = preferences.debug_mode
        #split = layout.split(factor=0.3)
        split = layout.row(align=True)
        
#        
        #split.prop(item, "info", icon='NONE', emboss=False, text=item.info)#"Index: %d" % (index)
        split.prop(item, "info", icon="NONE", emboss=(data.layers.active_index == index), text="")
        
        
#        icon_name = 'LOCKED' if item.lock else 'UNLOCKED'

        split.prop(item, "hide", icon='HIDE_OFF', emboss=False, text="")
        split.prop(item, "lock", icon='UNLOCKED', emboss=False, text="")
        split.active = (not item.lock)


def _draw_layers(self, layout, context):
    if not context.active_object or context.active_object.type != "GPENCIL":
        
        box = layout.box()
        col = box.column(align=True)
        row = col.row(align=True)
        row.label(text="Please select a greasepencil object", icon="NONE")
        
        return

    object = context.active_object

    # preferences = get_addon_preferences()
    props = context.scene.greasepencilfocus

    index = len(object.data.layers) - 1
    col = layout.column(align=True)
    # active_index = object.data.layers.active_index

    # log("draw layers, active index ")
    # log(active_index)

    row = col.row(align=True)
    row.prop(object, "name", icon="NONE", text="")
    col.separator()

    row = col.row(align=True)
    row.prop(props, 'auto_switch_tools', text="Auto switch tools")

    row = row.row(align=True)
    row.alignment = "RIGHT"
    #row.prop(props, 'auto_hide', text="", icon="HIDE_OFF")
    #row.prop(props, 'auto_lock', text="", icon="LOCKED")

    row.operator(SwitchLayersFadeOperator.bl_idname, text=" fade", icon= "HIDE_OFF" if context.space_data.overlay.use_gpencil_fade_layers else "HIDE_ON", emboss=False)
    row.operator(SwitchAutoLockOperator.bl_idname, text=" auto", icon="LOCKED" if object.data.use_autolock_layers else "UNLOCKED", emboss=False)

    col.separator()

    # is_debug = preferences.debug_mode

    if object.data and object.data.layers:
        # layers are displayed in reverse
        row = col.row()
        row.template_list("LAYERS_UL_items", "", object.data, "layers", object.data.layers, "active_index")
     

    # Add material button

    col.separator()

    row = col.row(align=True)
    row_lay = row.operator(SwitchToSubTabOperator.bl_idname, text="", icon="FILE_NEW",emboss=False)
    row_lay.tab_name = "ADD_LAYER"

    col.separator()
    row.alignment = "RIGHT"

    row_mat = row.operator(SwitchToSubTabOperator.bl_idname, text="", icon="MATERIAL",emboss=False)
    row_mat.tab_name = "MATERIALS"

    return index

class AddLayerOperator(bpy.types.Operator):
    bl_idname = 'greasepencilfocus.add_layer'
    bl_label = 'Add Layer'
    bl_description = "Add Layer"
    bl_options = {'REGISTER','UNDO'}
    
    def execute(self, context):
        addon_name = os.path.splitext(__name__)[0]

        props = context.scene.greasepencilfocus
        previous_index = context.active_object.data.layers.active_index
        bpy.ops.gpencil.layer_add()
        
        # layers are added on top of the previous active per default
        new_index = previous_index + 1
        if context.active_object.data.layers[new_index]:
            context.active_object.data.layers[new_index].info = props.add_layer_name

        if props.add_layer_position == 'BELOW':
            bpy.ops.gpencil.layer_move(type='DOWN')

        # save current settings for this layer
        save_last_tool()

        # go back to layers tab for the next popup opening
        props.tool_tab = "LAYERS"
        
        return {'FINISHED'}

class AddMaterialOperator(bpy.types.Operator):

    bl_idname = 'greasepencilfocus.add_material'
    bl_label = 'Add Material'
    bl_description = "Add Material"
    bl_options = {'REGISTER','UNDO'}
    
    def execute(self, context):
        addon_name = os.path.splitext(__name__)[0]

        # params = (
        #     context.scene.use_stroke,
        #     context.scene.stroke_color,
        #     context.scene.use_fill,
        #     context.scene.fill_color
        # )
        
        props = context.scene.greasepencilfocus

        mat = bpy.data.materials.new(props.add_mat_name)
        bpy.data.materials.create_gpencil_data(mat)
        mat.grease_pencil.show_stroke = props.add_mat_show_stroke
        mat.grease_pencil.color = props.add_mat_stroke_color
        mat.grease_pencil.show_fill = props.add_mat_show_fill
        mat.grease_pencil.fill_color = props.add_mat_fill_color

        bpy.ops.object.material_slot_add()
        idx = bpy.context.active_object.active_material_index
        bpy.context.active_object.material_slots[idx].material = mat

        save_last_tool()

        # switch sub tools tab to layers
        props.tool_tab = "LAYERS"
        
        return {'FINISHED'}

class SwitchToLayerOperator(Operator):
    bl_idname = "greasepencilfocus.switch_to_layer"
    bl_label = "Switch to Layer"
    bl_description = "Switch to this layer"
    bl_options = {'REGISTER','UNDO'}

    layer_index : IntProperty(default=0, name = "layer index")

    def execute(self, context):
        log("switch to layer:")
        log(self.layer_index)
        props = context.scene.greasepencilfocus

        context.active_object.data.layers.active_index = self.layer_index

        return {'FINISHED'}
class SwitchAutoLockOperator(Operator):
    bl_idname = "greasepencilfocus.switch_auto_lock"
    bl_label = "Auto lock inactive layers"
    bl_description = "All the layers except the one selected"
    bl_options = {'REGISTER','UNDO'}

    def execute(self, context):
        context.active_object.data.use_autolock_layers = not context.active_object.data.use_autolock_layers
        return {'FINISHED'}

class SwitchLayersFadeOperator(Operator):
    bl_idname = "greasepencilfocus.switch_layers_fade"
    bl_label = "Fade inactive layers"
    bl_description = "Fade inactive layers (options in overlay panel). Will switch away from 'RENDERED' viewport shading which dont support this effect"
    bl_options = {'REGISTER','UNDO'}

    def execute(self, context):
        context.space_data.overlay.use_gpencil_fade_layers = not context.space_data.overlay.use_gpencil_fade_layers

        
        if context.space_data.overlay.use_gpencil_fade_layers:
            # layers fade dont work in the RENDERED shading type. Switch to "MATERIAL" per default ? todo : retrieve the previous state on uncheck ?
            if context.space_data.shading.type == 'RENDERED':
                context.space_data.shading.type = 'MATERIAL'
            # automatically show overlays if not activated ? todo : retrieve previous state on uncheck ?
            if not context.space_data.overlay.show_overlays:
                context.space_data.overlay.show_overlays = True

        return {'FINISHED'}

class SwitchObjectsFadeOperator(Operator):
    bl_idname = "greasepencilfocus.switch_objects_fade"
    bl_label = "Fade inactive objects"
    bl_description = "Fade inactive objects (options in overlay panel). Will switch away from 'RENDERED' viewport shading which dont support this effect"
    bl_options = {'REGISTER','UNDO'}

    def execute(self, context):
        context.space_data.overlay.use_gpencil_fade_objects = not context.space_data.overlay.use_gpencil_fade_objects

        if context.space_data.overlay.use_gpencil_fade_objects:
            # layers fade dont work in the RENDERED shading type. Switch to "MATERIAL" per default ? todo : retrieve the previous state on unlock
            if context.space_data.shading.type == 'RENDERED':
                context.space_data.shading.type = 'MATERIAL'
            # automatically show overlays if not activated ? todo : retrieve previous state on uncheck ?
            if not context.space_data.overlay.show_overlays:
                context.space_data.overlay.show_overlays = True

        return {'FINISHED'}

class SwitchObjectsFadeGPOperator(Operator):
    bl_idname = "greasepencilfocus.switch_objects_fade_gp"
    bl_label = "Fade inactive GP objects"
    bl_description = "Fade inactive Greasepencil objects (options in overlay panel). Will switch away from 'RENDERED' viewport shading which dont support this effect"
    bl_options = {'REGISTER','UNDO'}

    def execute(self, context):
        context.space_data.overlay.use_gpencil_fade_gp_objects = not context.space_data.overlay.use_gpencil_fade_gp_objects

        if context.space_data.overlay.use_gpencil_fade_gp_objects:
            # layers fade dont work in the RENDERED shading type. Switch to "MATERIAL" per default ? todo : retrieve the previous state on unlock
            if context.space_data.shading.type == 'RENDERED':
                context.space_data.shading.type = 'MATERIAL'
            # automatically show overlays if not activated ? todo : retrieve previous state on uncheck ?
            if not context.space_data.overlay.show_overlays:
                context.space_data.overlay.show_overlays = True
            # greasepencil objects fade work only if normal objects fade is activated
            if not context.space_data.overlay.use_gpencil_fade_objects:
                context.space_data.overlay.use_gpencil_fade_objects = True

        return {'FINISHED'}

# class SwitchToObjectOperator(Operator):
#     bl_idname = "greasepencilfocus.switch_to_object"
#     bl_label = "Switch to Object"
#     bl_description = "Go to this Greasepencil Object"
#     bl_options = {'REGISTER','UNDO'}

#     object_name : StringProperty(default="", name = "object name")

#     def execute(self, context):
#         addon_name = os.path.splitext(__name__)[0]
#         log("switch to object:")
#         log(self.object_name)

#         props = context.scene.greasepencilfocus

#         # first, deselect previous object :
#         if context.active_object:
#             context.active_object.select_set(False)

#         # switch active object
#         bpy.context.view_layer.objects.active = bpy.context.view_layer.objects[self.object_name]#bpy.data.objects[self.object_name]

#         # finally set selection to new object
#         bpy.data.objects[self.object_name].select_set(True)

#         # if force draw mode activated and object is on other mode, switch to draw mode
#         if props.force_draw_mode and bpy.context.active_object.mode != 'PAINT_GPENCIL':
#             bpy.ops.object.mode_set(mode="PAINT_GPENCIL")

#         if props.save_view_on_object:
#             load_object_view_settings()

#         # switch the popup sub tab to layers
#         props.tool_tab = "LAYERS"

#         return {'FINISHED'}

class SwitchObjectVisibility(Operator):
    bl_idname = "greasepencilfocus.switch_object_property"
    bl_label = "Hide or show in viewport"
    bl_description = "Hide or show in viewport"
    bl_options = {'REGISTER','UNDO'}

    object_name : StringProperty(default="", name = "object name")

    def execute(self, context):
        addon_name = os.path.splitext(__name__)[0]
        object = bpy.data.objects[self.object_name]

        status = object.hide_get()
        object.hide_set(not status)

        return {'FINISHED'}

class SwitchToSubTabOperator(Operator):

    tab_name: StringProperty(default="LAYERS", name = "action name")

    bl_idname = "greasepencilfocus.switch_to_sub_tab"
    bl_label = "Add" # add layer or material. Todo : separate in 2 operators
    bl_description = "Add in this object" # add layer or material. Todo : separate in 2 operators
    bl_options = {'REGISTER','UNDO'}

    def execute(self, context):
        addon_name = os.path.splitext(__name__)[0]
        props = context.scene.greasepencilfocus
        props.tool_tab = self.tab_name
        return {'FINISHED'}

def register():
    bpy.utils.register_class(GREASEPENCILFOCUS_Props)
    bpy.utils.register_class(GreasePencilFocusAddonPreferences)
    bpy.utils.register_class(SwitchToLayerOperator)
    # bpy.utils.register_class(SwitchToObjectOperator)
    bpy.utils.register_class(SwitchAutoLockOperator)
    bpy.utils.register_class(SwitchLayersFadeOperator)
    bpy.utils.register_class(SwitchObjectsFadeOperator)
    bpy.utils.register_class(SwitchObjectsFadeGPOperator)
    bpy.utils.register_class(SwitchObjectVisibility)
    bpy.utils.register_class(AddMaterialOperator)
    bpy.utils.register_class(AddLayerOperator)
    bpy.utils.register_class(SwitchToSubTabOperator)
    bpy.utils.register_class(LaunchModal)
    #bpy.utils.register_class(ExamplePanel)
    bpy.utils.register_class(ColorItem)
    bpy.utils.register_class(LAYERS_UL_items)
    bpy.utils.register_class(clickInGpHistoryOperator)

    log("GP focus addon register")

    # hack : workspaces and scenes not immediately available, wait 0.5sec
    bpy.app.timers.register(init_context, first_interval=2.0)

    # persistent function
    bpy.app.handlers.load_post.append(on_reload)
    
    #bpy.types.Scene.colors = bpy.props.CollectionProperty(type=ColorItem)
    #bpy.context.scene.colors.add()

def unregister():
    bpy.utils.unregister_class(GREASEPENCILFOCUS_Props)
    bpy.utils.unregister_class(GreasePencilFocusAddonPreferences)
    bpy.utils.unregister_class(SwitchToLayerOperator)
    # bpy.utils.unregister_class(SwitchToObjectOperator)
    bpy.utils.unregister_class(SwitchAutoLockOperator)
    bpy.utils.unregister_class(SwitchLayersFadeOperator)
    bpy.utils.unregister_class(AddMaterialOperator)
    bpy.utils.unregister_class(SwitchObjectsFadeOperator)
    bpy.utils.unregister_class(SwitchObjectsFadeGPOperator)
    bpy.utils.unregister_class(SwitchObjectVisibility)
    bpy.utils.unregister_class(AddLayerOperator)
    bpy.utils.unregister_class(SwitchToSubTabOperator)
    bpy.utils.unregister_class(ColorItem)
    bpy.utils.unregister_class(LAYERS_UL_items)
    bpy.utils.unregister_class(clickInGpHistoryOperator)


    bpy.msgbus.clear_by_owner(bpy.types.Scene.greasepencilfocus)
    

    for ws in bpy.data.workspaces:
        bpy.msgbus.clear_by_owner(ws)
    #bpy.msgbus.clear_by_owner(bpy.context.workspace)

    
    #####*********** MODAL

    unregister_keymaps()

    bpy.utils.unregister_class(LaunchModal)
    #bpy.utils.unregister_class(ExamplePanel)
    
if __name__ == "__main__":
    register()