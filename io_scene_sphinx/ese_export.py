#  Copyright (c) 2020-2021 Swyter <swyterzone+sphinx@gmail.com>
#  SPDX-License-Identifier: Zlib

"""
Name: 'Eurocom Scene Export'
Blender: 4.3.2
Group: 'Export'
Tooltip: 'Blender ESE Exporter for EuroLand'
Authors: Swyter and Jmarti856
"""

import bpy
from math import degrees
from mathutils import Matrix
from datetime import datetime
from bpy_extras.node_shader_utils import PrincipledBSDFWrapper
from eland_utils import *

#-------------------------------------------------------------------------------------------------------------------------------
ESE_VERSION = '1.00'
EXPORT_TRI = True
EXPORT_NORMALS = True
EXPORT_UV=True
EXPORT_VERTEX_COLORS = True
EXPORT_APPLY_MODIFIERS=True

#SET BY USER
EXPORT_MESH = True
EXPORT_CAMERAS = True
EXPORT_LIGHTS = True
EXPORT_ANIMATIONS = True
EXPORT_MESH_ANIMATIONS = True
TRANSFORM_TO_CENTER = True
STATIC_FRAME = 1
DECIMAL_PRECISION = 6
df = f'%.{DECIMAL_PRECISION}f'
dcf = f'{{:>{DECIMAL_PRECISION}f}}'

#Global variables
FRAMES_COUNT = 0
TICKS_PER_FRAME = 0

#-------------------------------------------------------------------------------------------------------------------------------
def printCustomProperties(out):
    scene = bpy.context.scene
    custom_properties = {key: value for key, value in scene.items() if key not in '_RNA_UI'}

    #print only the visible ones
    visible_properties = {key: value for key, value in custom_properties.items() if isinstance(value, (int, float, str, bool))}
      
    type_mapping = {
        int: "Numeric",
        float: "Numeric",
        str: "String",
        bool: "Boolean"
    }      

    out.write('\t*SCENE_UDPROPS {\n')
    out.write('\t\t*PROP_COUNT\t%d\n' % len(visible_properties))
    
    for index, (key, value) in enumerate(visible_properties.items()):
        type_name = type_mapping.get(type(value), type(value).__name__)
        out.write('\t\t*PROP\t%d\t"%s"\t"%s"\t"%s"\n' % (index, key, type_name, value))
    out.write('\t}\n')

#-------------------------------------------------------------------------------------------------------------------------------
def write_scene_data(out, scene):
    global FRAMES_COUNT, TICKS_PER_FRAME

    #Get scene data
    first_frame = scene.frame_start
    last_frame = scene.frame_end
    frame_rate = scene.render.fps
    FRAMES_COUNT = last_frame - first_frame + 1

    tick_frequency = 4800 #Matches original examples
    TICKS_PER_FRAME = tick_frequency // frame_rate

    world_amb = scene.world.color if scene.world else (0.8, 0.8, 0.8)

    #Print scene data
    out.write("*SCENE {\n")
    out.write('\t*SCENE_FILENAME "%s"\n' % (bpy.data.filepath))
    out.write('\t*SCENE_FIRSTFRAME %s\n' % first_frame)
    out.write('\t*SCENE_LASTFRAME %s\n' % last_frame)
    out.write('\t*SCENE_FRAMESPEED %s\n' % frame_rate)
    out.write('\t*SCENE_TICKSPERFRAME %s\n' % TICKS_PER_FRAME)
    out.write(f'\t*SCENE_BACKGROUND_STATIC {df} {df} {df}\n' % (world_amb[0], world_amb[1], world_amb[2]))
    out.write(f'\t*SCENE_AMBIENT_STATIC {df} {df} {df}\n' % (world_amb[0], world_amb[1], world_amb[2]))
    printCustomProperties(out)
    out.write("}\n\n")
    
#-------------------------------------------------------------------------------------------------------------------------------
def write_material_data(out, mat, tab_level, base_material):

    tab = get_tabs(tab_level)
    out.write(f'{tab}*MATERIAL_NAME "%s"\n' % mat.name)
    out.write(f'{tab}*MATERIAL_CLASS "Standard"\n')

    # Envolver material para usar PrincipledBSDFWrapper
    mat_wrap = PrincipledBSDFWrapper(mat) if mat.use_nodes else None
        
    if mat_wrap:
        use_mirror = mat_wrap.metallic != 0.0
        use_transparency = mat_wrap.alpha != 1.0

        # The Ka statement specifies the ambient reflectivity using RGB values.
        if use_mirror:
            out.write(f'{tab}*MATERIAL_AMBIENT {df} {df} {df}\n' % (mat_wrap.metallic, mat_wrap.metallic, mat_wrap.metallic))
        else:
            out.write(f'{tab}*MATERIAL_AMBIENT {df} {df} {df}\n' % (1.0, 1.0, 1.0))
            
        # The Kd statement specifies the diffuse reflectivity using RGB values.
        out.write(f'{tab}*MATERIAL_DIFFUSE {df} {df} {df}\n' % mat_wrap.base_color[:3]) # Diffuse
        
        # XXX TODO Find a way to handle tint and diffuse color, in a consistent way with import...
        out.write(f'{tab}*MATERIAL_SPECULAR {df} {df} {df}\n' % (mat_wrap.specular, mat_wrap.specular, mat_wrap.specular))  # Specular

        shine = 1.0 - mat_wrap.roughness
        out.write(f'{tab}*MATERIAL_SHINE %.1f\n' % shine)
        
        transparency = 1.0 - mat_wrap.alpha
        out.write(f'{tab}*MATERIAL_TRANSPARENCY %.1f\n' % transparency)
                
        # Self-illumination (emission) of the material
        out.write(f'{tab}*MATERIAL_SELFILLUM %.1f\n' % mat_wrap.emission_strength)

        if base_material == False:
            #### And now, the image textures...
            image_map = {
                    "map_Kd": "base_color_texture",
                    #"map_Ka": None,  # ambient...
                    #"map_Ks": "specular_texture",
                    #"map_Ns": "roughness_texture",
                    #"map_d": "alpha_texture",
                    #"map_Tr": None,  # transmission roughness?
                    #"map_Bump": "normalmap_texture",
                    #"disp": None,  # displacement...
                    #"refl": "metallic_texture",
                    #"map_Ke": None  # emission...
                    }

            for key, mat_wrap_key in sorted(image_map.items()):
                if mat_wrap_key is None:
                    continue
                tex_wrap = getattr(mat_wrap, mat_wrap_key, None)
                if tex_wrap is None:
                    continue
                image = tex_wrap.image
                if image is None:
                    continue
                out.write(f'{tab}*MAP_DIFFUSE {{\n')
                out.write(f'{tab}\t*MATERIAL_NAME "%s"\n' % image.name)
                out.write(f'{tab}\t*MAP_CLASS "Bitmap"\n')
                if use_mirror:
                    out.write(f'{tab}\t*MAP_AMOUNT %.1f\n' % (mat_wrap.metallic))
                else:
                    out.write(f'{tab}\t*MAP_AMOUNT %.1f\n' % (1))                    
                texture_path = bpy.path.abspath(image.filepath)
                out.write(f'{tab}\t*BITMAP "%s"\n' % (texture_path))                                                
                out.write(f'{tab}}}\n')

#-------------------------------------------------------------------------------------------------------------------------------
def write_scene_materials(out):
    #Get scene materials, the key is the object name, the value is the mesh materials list
    mesh_materials = {}
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            material_list = []
            for mat_slot in obj.material_slots:
                if mat_slot.material:
                    material_list.append(mat_slot.material)
            mesh_materials[obj.name] = material_list

    # Print materials list                                        
    out.write("*MATERIAL_LIST {\n")
    out.write("\t*MATERIAL_COUNT %d\n" % len(mesh_materials))
    for index, (mesh_name, materials) in enumerate(mesh_materials.items()):
        out.write("\t*MATERIAL %d {\n" % index)
        
        materials_count = len(materials)
        if materials_count == 1:
            write_material_data(out, materials[0], 2, False)
        elif materials_count > 1:
            write_material_data(out, materials[0], 2, True)
            out.write("\t\t*MATERIAL_MULTIMAT\n")
            out.write("\t\t*NUMSUBMTLS %d\n" % materials_count)
            for submat_index, mat in enumerate(materials):
                out.write("\t\t*SUBMATERIAL %d {\n" % submat_index)
                write_material_data(out, mat, 3, False)
                out.write("\t\t}\n")
        out.write('\t}\n')            
    out.write('}\n')

    return mesh_materials

#-------------------------------------------------------------------------------------------------------------------------------
def write_tm_node(out, obj_matrix_data, isPivot = False):

    if isPivot:
        matrix_data = obj_matrix_data["matrix_transformed"]

        # Apply transform matrix
        if TRANSFORM_TO_CENTER:
            matrix_data = Matrix.Identity(4) 

        out.write('\t*NODE_PIVOT_TM {\n')
    else:
        matrix_data = obj_matrix_data["matrix_original"]

        # Apply transform matrix
        if not TRANSFORM_TO_CENTER:
            matrix_data = Matrix.Identity(4) 

        out.write('\t*NODE_TM {\n')

    out.write('\t\t*NODE_NAME "%s"\n' % (obj_matrix_data["name"]))
    out.write('\t\t*INHERIT_POS %d %d %d\n' % (0, 0, 0))
    out.write('\t\t*INHERIT_ROT %d %d %d\n' % (0, 0, 0))
    out.write('\t\t*INHERIT_SCL %d %d %d\n' % (0, 0, 0))
        
    #Calculate matrix rotations.... 
    eland_data = create_euroland_matrix(matrix_data, obj_matrix_data["type"])
    eland_matrix = eland_data["eland_matrix"]
    eland_euler = eland_data["eland_euler"]

    out.write(f'\t\t*TM_ROW0 {df} {df} {df}\n' % (eland_matrix[0].x, eland_matrix[1].x, eland_matrix[2].x))
    out.write(f'\t\t*TM_ROW1 {df} {df} {df}\n' % (eland_matrix[0].y, eland_matrix[1].y, eland_matrix[2].y))
    out.write(f'\t\t*TM_ROW2 {df} {df} {df}\n' % (eland_matrix[0].z, eland_matrix[1].z, eland_matrix[2].z))
    
    #Transform position
    obj_position = eland_matrix.translation
    out.write(f'\t\t*TM_ROW3 {df} {df} {df}\n' % (obj_position.x,obj_position.y,obj_position.z))
    out.write(f'\t\t*TM_POS {df} {df} {df}\n' % (obj_position.x,obj_position.y,obj_position.z))
    
    #Transform rotation
    out.write(f'\t\t*TM_ROTANGLE {df} {df} {df}\n' % (eland_euler.x, eland_euler.y, eland_euler.z))

    #Print scale
    transformed_scale = eland_matrix.to_scale()
    out.write(f'\t\t*TM_SCALE {df} {df} {df}\n' % (transformed_scale.x, transformed_scale.z, transformed_scale.y))
    out.write(f'\t\t*TM_SCALEANGLE {df} {df} {df}\n' % (0, 0, 0))
    out.write('\t}\n')

#-------------------------------------------------------------------------------------------------------------------------------
def write_animation_node(out, object_data, object_matrix_data):
    global TICKS_PER_FRAME
    
    out.write('\t*TM_ANIMATION {\n')
    out.write('\t\t*TM_ANIMATION "%s"\n' % object_data.name)

    frameIndex = 0 
    out.write('\t\t*TM_ANIM_FRAMES {\n')
    for f in range(bpy.context.scene.frame_start, bpy.context.scene.frame_end + 1):
        bpy.context.scene.frame_set(f)
               
        # Calculate frame index
        if f > 0:
            frameIndex += TICKS_PER_FRAME

        #Print rotation
        out.write('\t\t\t*TM_FRAME  {:<5d}'.format(frameIndex))

        eland_data = create_euroland_matrix(object_data.matrix_world.copy(), object_data.type)
        eland_matrix = eland_data["eland_matrix"]

        if not TRANSFORM_TO_CENTER:
            current_matrix = object_data.matrix_world.copy()        
            relative_matrix = current_matrix @ object_matrix_data["matrix_original"]
            eland_data = create_euroland_matrix(relative_matrix, object_data.type)
            eland_matrix = eland_data["eland_matrix"]
            eland_matrix.translation = (Matrix.Identity(4) @ current_matrix).translation

        out.write(f' {df} {df} {df}' % (eland_matrix[0].x, eland_matrix[1].x, eland_matrix[2].x))
        out.write(f' {df} {df} {df}' % (eland_matrix[0].y, eland_matrix[1].y, eland_matrix[2].y))
        out.write(f' {df} {df} {df}' % (eland_matrix[0].z, eland_matrix[1].z, eland_matrix[2].z))
        
        #Transform position
        obj_position = eland_matrix.translation
        out.write(f' {df} {df} {df}\n' % (obj_position.x, obj_position.y, obj_position.z))

    out.write('\t\t}\n')
    out.write('\t}\n')

#-------------------------------------------------------------------------------------------------------------------------------
def write_mesh_data(out, scene, depsgraph, scene_materials):
    for ob_main in scene.objects:
        # ignore dupli children
        if ob_main.parent and ob_main.parent.instance_type in {'VERTS', 'FACES'}:
            continue

        obs = [(ob_main, ob_main.matrix_world)]
        if ob_main.is_instancer:
            obs += [(dup.instance_object.original, dup.matrix_world.copy())
                    for dup in depsgraph.object_instances
                    if dup.parent and dup.parent.original == ob_main]
            # ~ print(ob_main.name, 'has', len(obs) - 1, 'dupli children')
            
        for ob, ob_mat in obs:
            ob_for_convert = ob.evaluated_get(depsgraph) if EXPORT_APPLY_MODIFIERS else ob.original

            try:
                me = ob_for_convert.to_mesh()
            except RuntimeError:
                me = None

            if me is None:
                continue

            # _must_ do this before applying transformation, else tessellation may differ
            if EXPORT_TRI:
                # _must_ do this first since it re-allocs arrays
                mesh_triangulate(me)

            # Create transform matrix
            if TRANSFORM_TO_CENTER:
                to_origin = Matrix.Identity(4)
                scale_matrix = Matrix.Diagonal(ob.scale).to_4x4()

                matrix_transformed = to_origin @ scale_matrix
            else:
                matrix_transformed = ob_mat
            
            # Apply transform matrix
            me.transform(MESH_GLOBAL_MATRIX @ matrix_transformed)

            obj_matrix_data = {
                "name" : ob_main.name,
                "type" : ob_main.type,
                "matrix_original" : ob_mat.copy(),
                "matrix_transformed": matrix_transformed.copy()
            }

            # If negative scaling, we have to invert the normals...
            if ob_mat.determinant() < 0.0:
                me.flip_normals()

            # Crear listas únicas de coordenadas de vértices, UVs y colores de vértices
            unique_vertices = list({tuple(v.co) for v in me.vertices})

            #Get UVs
            unique_uvs = []
            if EXPORT_UV:
                if me.uv_layers:
                    for uv_layer in me.uv_layers:
                        for loop in me.loops:
                            unique_uvs.append(tuple(uv_layer.data[loop.index].uv))
                    unique_uvs = list(set(unique_uvs))

            #Get colors
            unique_colors = []
            if EXPORT_VERTEX_COLORS:
                if me.vertex_colors:
                    for color_layer in me.vertex_colors:
                        for loop in me.loops:
                            unique_colors.append(tuple(color_layer.data[loop.index].color))
                    unique_colors = list(set(unique_colors))

            # Create mapping lists
            vertex_index_map = {v: idx for idx, v in enumerate(unique_vertices)}
            uv_index_map = {uv: idx for idx, uv in enumerate(unique_uvs)}
            color_index_map = {color: idx for idx, color in enumerate(unique_colors)}
            mesh_materials = scene_materials[ob_main.name]
            mesh_materials_names = [m.name if m else None for m in mesh_materials]
            
            # Start printing
            out.write("*GEOMOBJECT {\n")
            out.write('\t*NODE_NAME "%s"\n' % ob_main.name)
            write_tm_node(out, obj_matrix_data)
            write_tm_node(out, obj_matrix_data, True)

            #Mesh data
            out.write('\t*MESH {\n')
            out.write('\t\t*TIMEVALUE %d\n' % STATIC_FRAME)
            out.write('\t\t*MESH_NUMVERTEX %u\n' % len(unique_vertices))
            out.write('\t\t*MESH_NUMFACES %u\n' % len(me.polygons))

            #-------------------------------------------------------------------------------------------------------------------------------
            #Vertex lists
            out.write('\t\t*MESH_VERTEX_LIST {\n')
            for vindex, uv in enumerate(unique_vertices):
                out.write(f'\t\t\t*MESH_VERTEX  {{:>5d}}\t{dcf}\t{dcf}\t{dcf}\n'.format(vindex, uv[0], uv[1], uv[2]))
            out.write('\t\t}\n')    
            
            #Vertex mapping
            out.write('\t\t*MESH_FACE_LIST {\n')
            for p_index, poly in enumerate(me.polygons):
                
                vertex_indices = [vertex_index_map[tuple(me.vertices[v].co)] for v in (poly.vertices)]

                #Get material index
                material_index = -1
                if poly.material_index < len(me.materials):
                    material_name = me.materials[poly.material_index].name
                    if material_name in mesh_materials_names:
                        material_index = mesh_materials_names.index(material_name)
                
                # swy: the calc_loop_triangles() doesn't modify the original faces, and instead does temporary ad-hoc triangulation
                #      returning us a list of three loops per "virtual triangle" that only exists in the returned thingie
                #      i.e. len(tri_loop) should always be 3, but internally, for each loop .face we're a member of
                #           still has 4 vertices and the four (different) loops of an n-gon, and .link_loop_next
                #           points to the original model's loop chain; the loops of our triangle aren't really linked
                edges_from_ngon = []  # Almacenar el resultado para cada borde del triángulo
                for tri_idx in range(len(vertex_indices)):
                    is_from_ngon = tri_edge_is_from_ngon(poly, vertex_indices, tri_idx, me.loops)
                    edges_from_ngon.append(1 if is_from_ngon else 0)

                #Face Vertex Index
                out.write('\t\t\t*MESH_FACE    {:>3d}:    A: {:>6d} B: {:>6d} C: {:>6d}'.format(p_index, vertex_indices[0], vertex_indices[1], vertex_indices[2]))
                out.write('    AB: {:<6d} BC: {:<6d} CA: {:<6d}  *MESH_SMOOTHING   *MESH_MTLID {:<3d}\n'.format(edges_from_ngon[0], edges_from_ngon[1], edges_from_ngon[2], material_index))
            out.write('\t\t}\n')

            #-------------------------------------------------------------------------------------------------------------------------------
            if EXPORT_UV:
                #Print list
                out.write('\t\t*MESH_NUMTVERTEX %u\n' % len(unique_uvs))
                out.write('\t\t*MESH_TVERTLIST {\n')
                for uv_index, uv in enumerate(unique_uvs):
                    out.write(f'\t\t\t*MESH_TVERT {{:>5d}}\t{dcf}\t{dcf}\t{dcf}\n'.format(uv_index, uv[0], uv[1], 0))
                out.write('\t\t}\n')

                #Map UVs
                out.write('\t\t*MESH_NUMTVFACES %d\n' % len(me.polygons))
                out.write('\t\t*MESH_TFACELIST {\n')
                for p_index, poly in enumerate(me.polygons):
                    uv_indices = []
                    for loop_index in (poly.loop_indices):
                        uv = tuple(me.uv_layers.active.data[loop_index].uv)
                        uv_indices.append(uv_index_map.get(uv, -1))
                    out.write(f'\t\t\t*MESH_TFACE {{:<3d}}\t{dcf}\t{dcf}\t{dcf}\n'.format(p_index, uv_indices[0], uv_indices[1], uv_indices[2]))
                out.write('\t\t}\n')

            #-------------------------------------------------------------------------------------------------------------------------------
            if EXPORT_VERTEX_COLORS:
                #Print list
                out.write('\t\t*MESH_NUMCVERTEX %u\n' % len(unique_colors))
                out.write('\t\t*MESH_CVERTLIST {\n')
                for col_index, col  in enumerate(unique_colors):
                    out.write(f'\t\t\t*MESH_VERTCOL {{:>5d}}\t{dcf}\t{dcf}\t{dcf}\t{dcf}\n'.format(col_index, col[0], col[1], col[2], col[3]))
                out.write('\t\t}\n')

                #Map colors
                out.write('\t\t*MESH_NUMCVFACES %d\n' % len(me.polygons))
                out.write('\t\t*MESH_CFACELIST {\n')
                for p_index, poly in enumerate(me.polygons):
                    color_indices = []
                    for loop_index in (poly.loop_indices):
                        color = tuple(me.vertex_colors.active.data[loop_index].color)
                        color_indices.append(color_index_map.get(color, -1))
                    out.write(f'\t\t\t*MESH_CFACE {{:<3d}}\t{dcf}\t{dcf}\t{dcf}\n'.format(p_index, color_indices[0], color_indices[1], color_indices[2]))
                out.write('\t\t}\n')           

            #-------------------------------------------------------------------------------------------------------------------------------
            if EXPORT_NORMALS:
                out.write('\t\t*MESH_NORMALS {\n')
                for p_index, poly in enumerate(me.polygons):
                    poly_normals = poly.normal
                    vertex_indices = [vertex_index_map[tuple(me.vertices[v].co)] for v in (poly.vertices)]    
                
                    out.write(f'\t\t\t*MESH_FACENORMAL {{:<3d}}\t{dcf}\t{dcf}\t{dcf}\n'.format(p_index, poly_normals[0], poly_normals[1], poly_normals[2]))
                    for tri_idx in range(len(vertex_indices)):
                        out.write(f'\t\t\t\t*MESH_VERTEXNORMAL {{:<3d}}\t{dcf}\t{dcf}\t{dcf}\n'.format(tri_idx, poly_normals[0], poly_normals[1], poly_normals[2]))
                out.write('\t\t}\n')
        
            #Close mesh block
            out.write('\t}\n')

            #Print animations
            if EXPORT_MESH_ANIMATIONS:
                write_animation_node(out, ob_main, obj_matrix_data)

            out.write(f'\t*WIREFRAME_COLOR {df} {df} {df}\n' % (ob.color[0], ob.color[1], ob.color[2]))
            out.write('\t*MATERIAL_REF %d\n' % list(scene_materials.keys()).index(ob.name))
            out.write("}\n")

            # clean up
            ob_for_convert.to_mesh_clear()

#-------------------------------------------------------------------------------------------------------------------------------
def write_light_settings(out, light_object, current_frame, tab_level = 1):
    tab = get_tabs(tab_level)

    out.write(f'{tab}*LIGHT_SETTINGS {{\n')
    out.write(f'{tab}\t*TIMEVALUE %u\n' % current_frame)
    out.write(f'{tab}\t*COLOR {df} {df} {df}\n' % (light_object.color.r, light_object.color.g, light_object.color.b))
    out.write(f'{tab}\t*FAR_ATTEN {df} {df}\n' % (light_object.shadow_soft_size, light_object.cutoff_distance))
    if (light_object.type == 'SUN'):
        out.write(f'{tab}\t*HOTSPOT %u\n' % degrees(light_object.angle))
    else:
        out.write(f'{tab}\t*HOTSPOT %u\n' % 0)
    out.write(f'{tab}}}\n')

#-------------------------------------------------------------------------------------------------------------------------------
def write_light_data(out, scene, depsgraph):
    global FRAMES_COUNT

    for ob_main in scene.objects:
        # Check if the object is a light source
        if ob_main.type != 'LIGHT':
            continue

        # Handle object instances (duplicated lights)
        obs = [(ob_main, ob_main.matrix_world)]
        if ob_main.is_instancer:
            obs += [(dup.instance_object.original, dup.matrix_world.copy())
                    for dup in depsgraph.object_instances
                    if dup.parent and dup.parent.original == ob_main]
            # ~ print(ob_main.name, 'has', len(obs) - 1, 'dupli children')

        for ob, ob_mat in obs:
            ob_for_convert = ob.evaluated_get(depsgraph) if EXPORT_APPLY_MODIFIERS else ob.original

            try:
                # Extract the light data
                light_data = ob_for_convert.data
            except AttributeError:
                light_data = None

            if light_data is None:
                continue
            
            # Apply transformation matrix to light object
            obj_matrix_data = {
                "name" : ob_main.name,
                "type" : ob_main.type,
                "matrix_original" : ob_mat.copy(),
                "matrix_transformed": ob_mat.copy()
            }

            # If negative scaling, we need to invert the direction of light if it's directional
            if ob_mat.determinant() < 0.0 and light_data.type == 'SUN':
                # Invert the direction of a sun light (directional light)
                obj_matrix_data["direction"] = (-ob_for_convert.matrix_world.to_3x3() @ light_data.direction).normalized()

            # Print ligth data                
            out.write("*LIGHTOBJECT {\n")
            out.write('\t*NODE_NAME "%s"\n' % ob.name)
            out.write('\t*NODE_PARENT "%s"\n' % ob.name)
            
            type_lut = {}
            type_lut['POINT'] = 'Omni'
            type_lut['SPOT' ] = 'TargetSpot'
            type_lut['SUN'  ] = 'TargetDirect'
            type_lut['AREA' ] = 'TargetDirect' # swy: this is sort of wrong ¯\_(ツ)_/¯

            out.write('\t*LIGHT_TYPE %s\n' % type_lut[light_data.type]) #Seems that always used "Omni" lights in 3dsMax, in blender is called "Point"
            write_tm_node(out, obj_matrix_data)

            #---------------------------------------------[Light Props]---------------------------------------------
            if (light_data.use_shadow):
                out.write('\t*LIGHT_SHADOWS %s\n' % "On") #for now
            else:
                out.write('\t*LIGHT_SHADOWS %s\n' % "Off") #for now
            out.write('\t*LIGHT_DECAY %s\n' % "InvSquare") # swy: this is the only supported mode
            out.write('\t*LIGHT_AFFECT_DIFFUSE %s\n' % "Off") #for now
            if (light_data.specular_factor > 0.001):
                out.write('\t*LIGHT_AFFECT_SPECULAR %s\n' % "On") #for now
            else:
                out.write('\t*LIGHT_AFFECT_SPECULAR %s\n' % "Off") #for now
            out.write('\t*LIGHT_AMBIENT_ONLY %s\n' % "Off") #for now

            write_light_settings(out, light_data, STATIC_FRAME)

            #---------------------------------------------[Light Animation]---------------------------------------------
            if FRAMES_COUNT > 1 and EXPORT_ANIMATIONS:
                out.write('\t*LIGHT_ANIMATION {\n')
                previous_light_data = None
                frameIndex = 0

                for frame in range(scene.frame_start, scene.frame_end + 1):
                    scene.frame_set(frame)

                    # current frame data
                    try:
                        # Extract the light data
                        light_data = ob_for_convert.data
                    except AttributeError:
                        light_data = None

                    if light_data is None:
                        continue

                    if previous_light_data is None or \
                    (light_data.color != previous_light_data.color or
                        light_data.shadow_soft_size != previous_light_data.shadow_soft_size or
                        light_data.cutoff_distance != previous_light_data.cutoff_distance or
                        (light_data.type == 'SUN' and light_data.angle != previous_light_data.angle)):

                        # Si hay alguna propiedad diferente, escribimos la configuración de la luz
                        write_light_settings(out, light_data, frameIndex, 2)

                        # Actualizamos los datos anteriores con los datos actuales
                        previous_light_data = light_data
                        frameIndex += TICKS_PER_FRAME
                out.write('\t}\n')
                write_animation_node(out, ob_main, obj_matrix_data)
            out.write("}\n")

#-------------------------------------------------------------------------------------------------------------------------------
def userWantsCameraScript(scene):
    printScript = False
    
    if "cameraScriptEditor" in scene.keys():
        camera_script_value = scene["cameraScriptEditor"]
    
        # Comprueba si el valor es mayor a 0
        if isinstance(camera_script_value, (int, float)) and camera_script_value > 0:
            printScript = True
    return printScript

#-------------------------------------------------------------------------------------------------------------------------------
def write_script_camera(out):
    markers = [m for m in bpy.context.scene.timeline_markers if m.camera is not None]
    num_cameras = len(markers)

    out.write('\t*USER_DATA %u {\n' % 0)
    out.write('\t\tCameraScript = %u\n' % 1)
    out.write('\t\tCameraScript_numCameras = %u\n' % num_cameras)
    out.write('\t\tCameraScript_globalOffset = %u\n' % 0)

    # Recorrer los marcadores y generar la información requerida
    for idx, marker in enumerate(markers, start=1):
        name = marker.name
        position = marker.frame  # Keyframe del marcador
        camera = marker.camera

        # Obtener el primer y último keyframe de la cámara asociada
        if camera.animation_data and camera.animation_data.action:
            fcurves = camera.animation_data.action.fcurves
            keyframes = sorted(set(kp.co[0] for fc in fcurves for kp in fc.keyframe_points))
            first_keyframe = int(keyframes[0]) if keyframes else position
            last_keyframe = int(keyframes[-1]) if keyframes else position
            timeline_frame = position + (last_keyframe - first_keyframe)

            # Imprimir la información en el formato requerido
            out.write('\t\tCameraScript_camera%u = %s %u %u %u %u\n' % (idx, name, first_keyframe, last_keyframe, position, timeline_frame))
    out.write('\t}\n')

#-------------------------------------------------------------------------------------------------------------------------------
def write_camera_settings(out, camera_object, camera_data, current_frame, tab_level = 1):
    tab = get_tabs(tab_level)

    out.write(f'{tab}*CAMERA_SETTINGS {{\n')
    out.write(f'{tab}\t*TIMEVALUE %u\n' % current_frame)
    out.write(f'{tab}\t*CAMERA_NEAR %d\n' % (camera_object.clip_start))
    out.write(f'{tab}\t*CAMERA_FAR %d\n' % (camera_object.clip_end))
    out.write(f'{tab}\t*CAMERA_FOV {df}\n' % (camera_object.angle))
    #out.write(f'{tab}\t*CAMERA_TDIST {df}\n' % (camera_data.location.length))
    out.write(f'{tab}}}\n')

#-------------------------------------------------------------------------------------------------------------------------------
def write_camera_data(out, scene, depsgraph):
    global FRAMES_COUNT

    CamerasList = sorted([obj for obj in bpy.context.scene.objects if obj.type == 'CAMERA'], key=lambda obj: obj.name)

    for ob_main in CamerasList:
        # Check if the object is a camera source
        if ob_main.type != 'CAMERA':
            continue

        obs = [(ob_main, ob_main.matrix_world)]
        if ob_main.is_instancer:
            obs += [(dup.instance_object.original, dup.matrix_world.copy())
                    for dup in depsgraph.object_instances
                    if dup.parent and dup.parent.original == ob_main]
            # ~ print(ob_main.name, 'has', len(obs) - 1, 'dupli children')
            
        for ob, ob_mat in obs:
            ob_for_convert = ob.evaluated_get(depsgraph) if EXPORT_APPLY_MODIFIERS else ob.original

            try:
                camera_data = ob_for_convert.data
            except RuntimeError:
                camera_data = None

            if camera_data is None:
                continue
                        
            # Apply transformation matrix to camera object
            obj_matrix_data = {
                "name" : ob.name,
                "type" : ob_main.type,
                "matrix_original" : ob_mat.copy(),
                "matrix_transformed": ob_mat.copy()
            }
      
        # Imprime el bloque con las propiedades de la cámara
        out.write("*CAMERAOBJECT {\n")
        out.write('\t*NODE_NAME "%s"\n' % ob.name)
        out.write('\t*CAMERA_TYPE %s\n' % "target")
        write_tm_node(out, obj_matrix_data)
        write_camera_settings(out, camera_data, ob, STATIC_FRAME)

        #---------------------------------------------[Camera Animation]---------------------------------------------
        print(FRAMES_COUNT)
        if FRAMES_COUNT > 1 and EXPORT_ANIMATIONS:
            out.write('\t*CAMERA_ANIMATION {\n')
            previous_camera_data = None
            frameIndex = 0
            
            for frame in range(scene.frame_start, scene.frame_end + 1):
                scene.frame_set(frame)

                # current frame data
                try:
                    # Extract the light data
                    camera_data = ob_for_convert.data
                except AttributeError:
                    camera_data = None

                if camera_data is None:
                    continue

                if previous_camera_data is None or \
                (camera_data.clip_start != previous_camera_data.clip_start or
                    camera_data.clip_end != previous_camera_data.clip_end or
                    camera_data.angle != previous_camera_data.angle):

                    # Si hay alguna propiedad diferente, escribimos la configuración de la cámara
                    write_camera_settings(out, camera_data, ob, frameIndex, 2)

                    # Actualizamos los datos anteriores con los datos actuales
                    previous_camera_data = camera_data
                    frameIndex += TICKS_PER_FRAME
            out.write('\t}\n')
            write_animation_node(out, ob_main, obj_matrix_data)
            
            
        #-------------------------------------------------------------------------------------------------------------------------------
        # swy: Jmarti856 found that this is needed for the time range of each camera to show up properly in
        #      the script timeline, without this all of them cover the entire thing from beginning to end
        #-------------------------------------------------------------------------------------------------------------------------------
        if ob_main == CamerasList[-1]:
            if userWantsCameraScript(scene):
                    write_script_camera(out)            
        out.write("}\n")

#-------------------------------------------------------------------------------------------------------------------------------
def export_file(filepath):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    scene = bpy.context.scene

    # Exit edit mode before exporting, so current object states are exported properly.
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')

    # Set the first frame
    bpy.context.scene.frame_set(0)

    # Create text file
    with open(filepath, 'w', encoding="utf8",) as out:
        # Header data
        out.write("*3DSMAX_EUROEXPORT	300\n")
        out.write('*COMMENT "Eurocom Export Version  3.00 - %s\n' % datetime.now().strftime("%A %B %d %Y %H:%M"))
        out.write('*COMMENT "Version of Blender that output this file: %s"\n' % bpy.app.version_string)
        out.write('*COMMENT "Version of ESE Plug-in: %s"\n\n' % ESE_VERSION)

        write_scene_data(out, scene)
        
        #scene objects data
        if EXPORT_MESH:
            scene_materials = write_scene_materials(out)
            write_mesh_data(out, scene, depsgraph, scene_materials)    
        if EXPORT_CAMERAS:
            write_camera_data(out, scene, depsgraph)
        if EXPORT_LIGHTS:
            write_light_data(out, scene, depsgraph)
                
    print(f"Archivo exportado con éxito: {filepath}")

#-------------------------------------------------------------------------------------------------------------------------------
filepath = bpy.path.abspath("C:\\Users\\Jordi Martinez\\Desktop\\EuroLand Files\\3D Examples\\test.ESE")  # Cambia la ruta si es necesario
export_file(filepath)