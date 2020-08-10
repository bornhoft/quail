import numpy as np
import meshing.meshbase as mesh_defs
import meshing.tools as mesh_tools

# TODO: This whole thing only works for triangles. Generalize this.
def adapt(solver, physics, mesh, stepper):
    """Adapt the mesh by refining or coarsening it.
    For now, this does very little - just splits an element in half.

    Arguments:
    solver - Solver object (solver/base.py)
    physics - Physics object (physics/base.py)
    mesh - Mesh object (meshing/meshbase.py)
    stepper - Stepper object (timestepping/stepper.py)
    """

    # Array of flags for which elements to be split
    needs_refinement = np.zeros(mesh.num_elems, dtype=bool)
    # Split element 0 and 1
    needs_refinement[0] = True
    needs_refinement[1] = True

    # Loop over all elements
    for elem_id in range(mesh.num_elems):
        # Only refine elements that need refinement
        if needs_refinement[elem_id]:

            # TODO: Find the neighbors

            # Get element
            elem = mesh.elements[elem_id]

            # -- Figure out what face to split -- #
            # Get info about the longest face of the element
            long_face, long_face_node_ids = find_longest_face(elem, mesh)
            # Get neighbor across this face
            neighbor = mesh.elements[elem.face_to_neighbors[long_face]]
            # Get the midpoint of this face
            midpoint = np.mean(mesh.node_coords[long_face_node_ids], axis=0)
            # Add the midpoint as a new mesh node
            mesh.node_coords = np.append(mesh.node_coords, [midpoint], axis=0)
            midpoint_id = np.size(mesh.node_coords, axis=0) - 1
            # Find which node on the long face is most counterclockwise (since
            # nodes must be ordered counterclockwise)
            ccwise_node_id, cwise_node_id = find_counterclockwise_node(elem.node_ids,
                    long_face_node_ids[0], long_face_node_ids[1])

            # The four split elements generated must contain:
            # 1. this midpoint
            # 2. the node opposite the long face
            # 3. one of the nodes that compose the long face (one for each)
            # and they must be in counterclockwise order.
            opposing_node_id = np.setdiff1d(elem.node_ids, long_face_node_ids, assume_unique=True)[0]
            neighbor_opposing_node_id = np.setdiff1d(neighbor.node_ids, long_face_node_ids, assume_unique=True)[0]
            neighbor_long_face = np.argwhere(neighbor.node_ids == neighbor_opposing_node_id)[0,0]
            new_nodes1 = np.array([opposing_node_id, midpoint_id, ccwise_node_id])
            new_nodes2 = np.array([opposing_node_id, cwise_node_id, midpoint_id])
            new_nodes3 = np.array([midpoint_id, neighbor_opposing_node_id, ccwise_node_id])
            new_nodes4 = np.array([midpoint_id, cwise_node_id, neighbor_opposing_node_id])

            # Create first element
            new_elem1 = append_element(mesh, new_nodes1, 1, elem, long_face - 2)
            # Create second element
            new_elem2 = append_element(mesh, new_nodes2, 2, elem, long_face - 1)
            # Create third element
            new_elem3 = append_element(mesh, new_nodes3, 0, neighbor, neighbor_long_face - 1)
            # Create fourth element
            new_elem4 = append_element(mesh, new_nodes4, 0, neighbor, neighbor_long_face - 2)

            print(new_elem1.face_to_neighbors)
            print(new_elem2.face_to_neighbors)
            print(new_elem3.face_to_neighbors)
            print(new_elem4.face_to_neighbors)

            # Create the faces between the elements
            append_face(mesh, new_elem1, new_elem2, 2, 1)
            append_face(mesh, new_elem3, new_elem4, 2, 1)
            append_face(mesh, new_elem1, new_elem3, 0, 1)
            append_face(mesh, new_elem2, new_elem4, 0, 2)

            # TODO: Figure out how to remove long face after making new ones

            # "Deactivate" the original element and its neighbor
            # TODO: figure out a better way to do this
            elem.face_to_neighbors = np.array([-1,-1,-1])
            neighbor.face_to_neighbors = np.array([-1,-1,-1])
            centroid = (midpoint + mesh.node_coords[opposing_node_id])/2
            neighbor_centroid = (midpoint + mesh.node_coords[neighbor_opposing_node_id])/2
            elem.node_coords = np.array([centroid, centroid+[.001,0], centroid+[.001,.001]])
            neighbor.node_coords = np.array([neighbor_centroid, neighbor_centroid+[.001,0], neighbor_centroid+[.001,.001]])

            # TODO: Update this correctly
            solver.elem_operators.x_elems = np.append(solver.elem_operators.x_elems, [solver.elem_operators.x_elems[-1,:,:]], axis=0)
            solver.elem_operators.x_elems = np.append(solver.elem_operators.x_elems, [solver.elem_operators.x_elems[-1,:,:]], axis=0)
            solver.elem_operators.x_elems = np.append(solver.elem_operators.x_elems, [solver.elem_operators.x_elems[-1,:,:]], axis=0)
            solver.elem_operators.x_elems = np.append(solver.elem_operators.x_elems, [solver.elem_operators.x_elems[-1,:,:]], axis=0)

            # Call compute operators
            solver.precompute_matrix_operators()

            # -- Update solution -- #
            # TODO: map solution from old elements to new split elements
            # Append to the end of U
            physics.U = np.append(physics.U, [physics.U[-1,:,:]], axis=0)
            physics.U = np.append(physics.U, [physics.U[-1,:,:]], axis=0)
            physics.U = np.append(physics.U, [physics.U[-1,:,:]], axis=0)
            physics.U = np.append(physics.U, [physics.U[-1,:,:]], axis=0)
            # Delete residual
            stepper.R = None

    # Just printing random things to check them out
    #print(mesh.node_coords)
    #for i in range(mesh.num_interior_faces):
    #    print("Face ", i)
    #    print(mesh.interior_faces[i].elemL_id)
    #    print(mesh.interior_faces[i].elemR_id)
    #    print(mesh.interior_faces[i].faceL_id)
    #    print(mesh.interior_faces[i].faceR_id)
    #print(mesh.boundary_groups)
    #for i in range(mesh.num_elems):
    #        print(mesh.elements[i].id)
    #        print(mesh.elements[i].node_ids)
    #        print(mesh.elements[i].node_coords)
    #        print(mesh.elements[i].face_to_neighbors)

def append_element(mesh, node_ids, face_id, parent, parent_face_id):
    """Create a new element at specified nodes and append it to the mesh.
    This function creates a new element and sets the neighbors of the element
    and neighbor element across the face specified by face_id.

    Arguments:
    mesh - Mesh object (meshing/meshbase.py)
    node_ids - array of new element's node IDs
    face_id - local ID of face in new element which needs new neighbors
    parent - Element object (meshing/meshbase.py), parent of the new element
    parent_face_id - local ID of face in parent element which needs new neighbors
    Returns:
    elem - Element object (meshing/meshbase.py), newly created element
    """
    # Create element
    mesh.elements.append(mesh_defs.Element())
    elem = mesh.elements[-1]
    # Set first element's id, node ids, coords, and neighbors
    elem.id = len(mesh.elements) - 1
    elem.node_ids = node_ids
    elem.node_coords = mesh.node_coords[elem.node_ids]
    elem.face_to_neighbors = np.full(mesh.gbasis.NFACES, -1)
    # Append to element nodes in mesh
    mesh.elem_to_node_ids = np.append(mesh.elem_to_node_ids, [node_ids], axis=0)
    # Update number of elements
    mesh.num_elems += 1
    # Get parent's neighbor across face
    parent_neighbor_id = parent.face_to_neighbors[parent_face_id]
    # Add parent's neighbor to new elements's neighbor
    elem.face_to_neighbors[face_id] = parent_neighbor_id
    # If the parent's neighbor is not a boundary, update it
    if parent_neighbor_id != -1:
        # Get parent's neighbor
        parent_neighbor = mesh.elements[parent_neighbor_id]
        # Get index of face in parent's neighbor
        parent_neighbor_face_index = np.argwhere(parent_neighbor.face_to_neighbors == parent.id)[0]
        # Set new element as parent neighbor's neighbor
        parent_neighbor.face_to_neighbors[parent_neighbor_face_index] = elem.id
        # Update old face neighbors by looking for the face between parent and parent_neighbor
        for face in mesh.interior_faces:
            if face.elemL_id == parent.id and face.elemR_id == parent_neighbor.id:
                face.elemL_id = elem.id
                face.faceL_id = face_id
                break
            if face.elemR_id == parent.id and face.elemL_id == parent_neighbor.id:
                face.elemR_id = elem.id
                face.faceR_id = face_id
                break
    return elem

def append_face(mesh, elem1, elem2, faceL_id, faceR_id):
    """Create a new face between two elements and append it to the mesh.

    Arguments:
    mesh - Mesh object (meshing/meshbase.py)
    elem1 - first Element object, left of face (meshing/meshbase.py)
    elem2 - second Element object, right of face (meshing/meshbase.py)
    faceL_id - index of node opposite the new face in elem1
    faceR_id - index of node opposite the new face in elem2
    """
    # Create the face between the elements
    mesh.interior_faces.append(mesh_defs.InteriorFace())
    mesh.interior_faces[-1].elemL_id = elem1.id
    mesh.interior_faces[-1].elemR_id = elem2.id
    mesh.interior_faces[-1].faceL_id = faceL_id
    mesh.interior_faces[-1].faceR_id = faceR_id
    # Set neighbors on either side of the face
    elem1.face_to_neighbors[faceL_id] = elem2.id
    elem2.face_to_neighbors[faceR_id] = elem1.id
    # Update number of faces
    mesh.num_interior_faces += 1

def find_longest_face(elem, mesh):
    """Find the longest face in an element.

    Arguments:
    elem - Element object (meshing/meshbase.py)
    mesh - Mesh object (meshing/meshbase.py)
    Returns:
    (int, array[2]) - tuple of longest face ID and array of node IDs
    """
    # Arrays for area of each face and face nodes
    face_areas = np.empty(mesh.gbasis.NFACES)
    face_node_ids = np.empty((mesh.gbasis.NFACES, 2), dtype=int)
    # Loop over each face
    for i in range(mesh.gbasis.NFACES):
        # If it's a boundary, skip it
        if elem.face_to_neighbors[i] == -1: continue
        # Get the neighbor across the face
        face_neighbor = mesh.elements[elem.face_to_neighbors[i]]
        # Calculate the face area and find face nodes
        face_areas[i], face_node_ids[i,:] = face_geometry_between(elem,
                face_neighbor, mesh.node_coords)
    # Get face with highest area
    long_face = np.argmax(face_areas)
    # Get node IDs of the longest face
    long_face_node_ids = face_node_ids[long_face,:]
    return (long_face, long_face_node_ids)

# TODO: If elem1 and elem2 are not actually neighbors, bad things will happen!
def face_geometry_between(elem1, elem2, node_coords):
    """Find the area and nodes of the face shared by two elements.

    Arguments:
    elem1 - first Element object (meshing/meshbase.py)
    elem2 - second Element object (meshing/meshbase.py)
    node_coords - array of node coordinates, shape [num_nodes, dim]
    Returns:
    (float, array[2]) tuple of face area and node IDs
    """
    # Find the node IDs of the face. This works by finding which two nodes
    # appear in both the current element and the neighbor across the face.
    face_node_ids = np.intersect1d(elem1.node_ids, elem2.node_ids)
    # Get the coordinates of these nodes
    face_nodes = node_coords[face_node_ids,:]
    # Return the area of the face (which is just the distance since this is a 2D
    # code)
    return (np.linalg.norm(face_nodes[0,:] - face_nodes[1,:]), face_node_ids)

def find_counterclockwise_node(nodes, a, b):
    """Find which of two neighboring nodes is more counterclockwise.
    The function takes an array of nodes along with two neighboring nodes a and b, then
    finds which of a and b are more counterclockwise. The nodes array is assumed
    to be ordered counterclockwise, which means that whichever of a and b
    appears later in the array (or appears at index 0) is the most counterclockwise.

    Arguments:
    nodes - array of node IDs
    a - ID of the first node
    b - ID of the second node
    Returns
    (int, int) tuple of counterclockwise node and clockwise node
    """

    # Find indices of a and b in the nodes array
    a_index = np.argwhere(nodes == a)[0]
    b_index = np.argwhere(nodes == b)[0]

    # If a's index is higher and b is not zero, then a is ahead
    if a_index > b_index and b_index != 0:
        ccwise_node = a
        cwise_node = b
    # Otherwise, if a_index is 0, the b must be at the end of the array, which
    # means a is ahead
    elif a_index == 0:
        ccwise_node = a
        cwise_node = b
    # Otherwise, a_index is lower than b_index and a_index is not index 0, so b
    # must be ahead
    else:
        ccwise_node = b
        cwise_node = a
    return (ccwise_node, cwise_node)
