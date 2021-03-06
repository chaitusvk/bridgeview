"""Modify object structure according to user-defined groups."""
import json
import numpy as np
import bpy  # pylint: disable=import-error
from . import helpers


def translate_group(group, translate):
    """Translate all objects in group list by translate."""
    bpy.ops.object.select_all(action='DESELECT')
    for name in group:
        bpy.data.objects[name].select = True
    bpy.ops.transform.translate(value=translate)
    bpy.ops.object.select_all(action='DESELECT')


def scale_object(obj, value: float, axis):
    """Scale an object by value along axis."""
    bpy.ops.object.select_all(action='DESELECT')
    bpy.data.scenes[0].objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.transform.resize(value=(axis*(value - 1) + np.ones(3)))
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.scenes[0].objects.active = None


class Scale():
    """Scaling operations."""

    def __init__(self, groups: dict=None):
        """Scaling class with groups scale, min, max defined in groups."""
        self.groups = groups

    def load_groups(self, filename: str, name: str):
        """Load groups definition from file by name."""
        with open(filename) as file:
            data = json.load(file)
            self.groups = data[name]

    def write_groups(self, filename: str, name: str, overwrite=True):
        """Write groups definition to file, or update an existing one."""
        with open(filename) as file:
            data = json.load(file)
        with open(filename, 'w') as file:
            if name not in data or overwrite:
                data[name] = self.groups
                json.dump(data, file)
            else:
                raise ValueError(
                    "Name already exists, specify overwrite to write anyway")

    def scale(self, value: float, axis_index: int,
              reference: str, base: str='scale'):
        """Scale by value along axis and translate other groups accordingly.

        The 'scale' group is scaled with end structures
        translated. All groups are translated to have the group
        provided as `base` remain stationary.

        """
        assert self.groups is not None, "Groups not defined."
        # Set axis
        axis = np.zeros(3, dtype=bool)
        axis[axis_index] = True

        # Scale the reference object
        start_ref = helpers.bounding_box(bpy.data.objects[reference])
        scale_object(bpy.data.objects[reference], value, axis)
        end_ref = helpers.bounding_box(bpy.data.objects[reference])

        # Resize scale group using offsets as end structures should be
        # translated without scaling
        for name in self.groups['scale']:
            if name == reference:
                continue
            start_box = helpers.bounding_box(bpy.data.objects[name])
            start_length = start_box[1] - start_box[0]
            end_box = start_box - start_ref + end_ref
            end_length = end_box[1] - end_box[0]
            scale_object(bpy.data.objects[name], end_length/start_length, axis)

        # Translate the groups according to base selection
        translate = (end_ref - start_ref)*axis
        if base == 'min':
            translate_group(self.groups['scale'], -translate[0])
            translate_group(self.groups['max'], translate[1] - translate[0])
        elif base == 'scale':
            translate_group(self.groups['min'], translate[0])
            translate_group(self.groups['max'], translate[1])
        elif base == 'max':
            translate_group(self.groups['min'], translate[0] - translate[1])
            translate_group(self.groups['scale'], -translate[1])
        else:
            raise ValueError(
                "Translate failed: base group name invalid {:s}".format(base))


def dissolve_near(point, obj):
    """Dissolve all vertices near coordinate point."""
    # Deselect all vertices
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    # Find and select nearby vertices
    for vert in obj.data.vertices:
        length = (vert.co - point).length
        if length < 0.5:
            vert.select = True
    # Dissolve vertices
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.dissolve_verts()
    bpy.ops.object.mode_set(mode='OBJECT')


def dissolve_near_selected_vertex(obj):
    """Dissolve all vertices near the selected vertex in the tree."""
    bpy.ops.object.mode_set(mode='OBJECT')
    selected_vertex = [vert for vert in obj.data.vertices if vert.select]
    if len(selected_vertex) == 1:
        dissolve_near(selected_vertex[0].co, obj)
    else:
        raise ValueError("Exactly one vertex must be selected.")


def limit_dissolve(obj, axis_index, limit):
    """Dissolve the vertices with coordinates below the limit along axis."""
    bpy.ops.object.select_all(action='DESELECT')
    bpy.data.scenes[0].objects.active = obj

    def dissolve_next():
        """Dissolve next vertex group and return True, else return False."""
        for vert in obj.data.vertices:
            if vert.co[axis_index] < limit:
                dissolve_near(vert.co, obj)
                return True
        return False
    while dissolve_next():
        pass
    bpy.data.scenes[0].objects.active = None
