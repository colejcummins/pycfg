from .cfg import CFG
from .node import Node, Location, Event
from typing import Any, List, Set
import ast


class CFGBuilder(ast.NodeVisitor):
  cfg: CFG
  cur_event: Event
  interrupting: bool
  loop_headers: List[Node]
  loop_exits: List[Node]


  def __init__(self):
    self._init_instances()
    super().__init__()


  def build(self, node: ast.AST) -> CFG:
    self.cfg = CFG('test', 'root', 'root', {'root': Node('root')})
    self._init_instances()
    if hasattr(node, 'body'):
      self._visit_block(node.body)
    else:
      self.visit(node)
    return self.cfg


  def _init_instances(self):
    self.cur_event = Event.PASS
    self.interrupting = False
    self.loop_headers = []
    self.loop_exits = []


  def _visit_block(self, nodes: List[ast.stmt | ast.expr]) -> None:
    for node in nodes:
      if self.interrupting:
        break
      self.visit(node)


  def generic_visit(self, node: ast.AST) -> Any:
    if self.cur_event != Event.PASS:
      cfg_node = self._build_node(node)
      self.cfg.attach_child(cfg_node, self.cur_event)
      self.cfg.go_to(cfg_node.name)
      self.cur_event = Event.PASS
    else:
      self.cfg.get_cur().append_contents(node)


  def visit_While(self, node: ast.While) -> Any:
    self._visit_loop(node)


  def visit_For(self, node: ast.For) -> Any:
    self._visit_loop(node)


  def _visit_loop(self, node: ast.For | ast.While) -> Any:
    cfg_node = self._build_node(node)
    exit_node = self._build_empty_node(f"exit_{cfg_node.name}", Location.default_end(node))
    self.loop_headers.append(cfg_node)
    self.loop_exits.append(exit_node)
    self.cfg.attach_child(cfg_node, self.cur_event)
    self.cfg.go_to(cfg_node.name)

    if node.body:
      self._visit_body(node, cfg_node, cfg_node.name)

    if node.orelse:
      self.cur_event = Event.ONFALSE
      self._visit_block(node.orelse)

    self._add_exit(exit_node)
    self.cfg.go_to(exit_node.name)

    self.loop_headers.pop()
    self.loop_exits.pop()


  def visit_If(self, node: ast.If) -> Any:
    cfg_node = self._build_node(node)
    exit_node = self._build_empty_node(f"exit_{cfg_node.name}", Location.default_end(node))
    self.cfg.attach_child(cfg_node, self.cur_event)
    self.cfg.go_to(cfg_node.name)

    if node.body:
      self._visit_body(node, exit_node, cfg_node.name)

    if node.orelse:
      self.cur_event = Event.ONFALSE
      self._visit_block(node.orelse)

    self._add_exit(exit_node)
    self.cfg.go_to(exit_node.name)


  def visit_Return(self, node: ast.Return) -> Any:
    self._visit_interrupts(node)


  def visit_Yield(self, node: ast.Yield) -> Any:
    self._visit_interrupts(node)


  def visit_YieldFrom(self, node: ast.YieldFrom) -> Any:
    # TODO
    self._visit_interrupts(node)


  def _visit_interrupts(self, node: ast.AST) -> Any:
    self.cfg.attach_child(self._build_node(node))
    self.interrupting = True


  def visit_Break(self, node: ast.Break) -> Any:
    self.cfg.attach_child(cfg_node := self._build_node(node))
    self.cfg.go_to(cfg_node.name)
    self.cfg.attach_child(self.loop_exits[-1], Event.ONBREAK)
    self.interrupting = True


  def visit_Continue(self, node: ast.Continue) -> Any:
    self.cfg.attach_child(cfg_node := self._build_node(node))
    self.cfg.go_to(cfg_node.name)
    self.cfg.attach_child(self.loop_headers[-1], Event.ONCONTINUE)
    self.interrupting = True


  def _visit_body(self, node: ast.AST, exit: Node, parent_name: str):
    self.cur_event = Event.ONTRUE
    self._visit_block(node.body)
    self._add_exit(exit)
    self.cfg.go_to(parent_name)


  def _add_exit(self, exit_node: Node):
    if self.interrupting:
      self.interrupting = False
    else:
      self.cfg.attach_child(exit_node)


  def _build_node(self, node: ast.AST, name: str = '') -> Node:
    return Node(
      name=name or f"{node.__class__.__name__}_{node.lineno}_{node.col_offset}",
      start=Location.default_start(node),
      end=Location.default_end(node),
      contents=[node]
    )


  def _build_empty_node(self,  name: str, location: Location) -> Node:
    return Node(name=name, start=location, end=location)


def builds(source: str) -> CFG:
  """Takes a python source string and returns the corresponding CFG"""
  return CFGBuilder().build(ast.parse(source))