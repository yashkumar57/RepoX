import type { RepositoryGraphResponse } from '@/lib/api'

export const INITIAL_GRAPH_NODE_LIMIT = 36
export const MAX_GRAPH_NODE_LIMIT = 96

export function initialGraphNodeIds(
  graph: RepositoryGraphResponse,
  limit = INITIAL_GRAPH_NODE_LIMIT,
): string[] {
  const degree = new Map<string, number>()
  for (const edge of graph.edges) {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1)
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1)
  }
  return [...graph.nodes]
    .sort((left, right) => (degree.get(right.id) ?? 0) - (degree.get(left.id) ?? 0) || left.id.localeCompare(right.id))
    .slice(0, limit)
    .map(node => node.id)
}

export function expandGraphNodeIds(
  graph: RepositoryGraphResponse,
  currentIds: Iterable<string>,
  nodeId: string,
  limit = MAX_GRAPH_NODE_LIMIT,
): string[] {
  const ids = new Set(currentIds)
  ids.add(nodeId)
  const neighbors = graph.edges
    .filter(edge => edge.source === nodeId || edge.target === nodeId)
    .flatMap(edge => [edge.source, edge.target])
    .filter(id => id !== nodeId)
    .sort()
  for (const neighbor of neighbors) {
    if (ids.size >= limit) break
    ids.add(neighbor)
  }
  return [...ids]
}

export function graphNodePositions(ids: string[]): Map<string, { x: number; y: number }> {
  const columns = Math.max(1, Math.ceil(Math.sqrt(ids.length * 1.6)))
  const rows = Math.max(1, Math.ceil(ids.length / columns))
  return new Map(ids.map((id, index) => ({
    id,
    x: 90 + (index % columns) * (820 / Math.max(columns - 1, 1)),
    y: 70 + Math.floor(index / columns) * (460 / Math.max(rows - 1, 1)),
  })).map(point => [point.id, point]))
}
