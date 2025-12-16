from .ast_nodes import Node

class NodeVisitor:
    def visit(self, node: Node):
        """
        Dynamically dispatch to a method named 'visit_ClassName'.
        """
        method_name = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: Node):
        """
        Fallback for nodes without a specific visitor method.
        Usually visits children to ensure the tree traversal continues.
        """
        raise NotImplementedError(f"No visit method for {node.__class__.__name__}")
