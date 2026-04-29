// SPDX-FileCopyrightText: 2025 Weibo, Inc.
//
// SPDX-License-Identifier: Apache-2.0

/**
 * DingtalkDocSelector - DingTalk document selector with cascade selection.
 *
 * Renders a tree of DingTalk documents with checkbox selection.
 * Selecting a folder automatically selects all its children.
 */

'use client'

import { useState, useCallback, useEffect, useMemo } from 'react'
import { Folder, FolderOpen, ChevronRight, ChevronDown, FileText } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/hooks/useTranslation'
import { dingtalkDocApi } from '@/apis/dingtalk-doc'
import { Checkbox } from '@/components/ui/checkbox'
import type { DingtalkDocNode } from '@/types/dingtalk-doc'
import type { DingtalkDocContext } from '@/types/context'

interface DingtalkDocSelectorProps {
  /** Selected contexts */
  selectedContexts: DingtalkDocContext[]
  /** Selection change callback */
  onSelectionChange: (contexts: DingtalkDocContext[]) => void
  /** Search value */
  searchValue?: string
}

interface TreeNodeProps {
  node: DingtalkDocNode
  level: number
  selectedIds: Set<string>
  expandedIds: Set<string>
  onToggleExpand: (nodeId: string) => void
  onToggleSelect: (node: DingtalkDocNode, selected: boolean) => void
  searchValue?: string
}

/**
 * Get all child document IDs recursively
 */
function getAllChildDocIds(node: DingtalkDocNode): string[] {
  const ids: string[] = []
  if (node.node_type !== 'folder') {
    ids.push(node.dingtalk_node_id)
  }
  if (node.children) {
    for (const child of node.children) {
      ids.push(...getAllChildDocIds(child))
    }
  }
  return ids
}

/**
 * Check node selection state considering cascade
 */
function getNodeSelectionState(
  node: DingtalkDocNode,
  selectedIds: Set<string>
): { selected: boolean; indeterminate: boolean } {
  // For folders, check all descendant documents
  if (node.node_type === 'folder' && node.children && node.children.length > 0) {
    const allDocIds = getAllChildDocIds(node)
    if (allDocIds.length === 0) {
      return { selected: false, indeterminate: false }
    }

    const selectedCount = allDocIds.filter(id => selectedIds.has(id)).length

    if (selectedCount === 0) {
      return { selected: false, indeterminate: false }
    } else if (selectedCount === allDocIds.length) {
      return { selected: true, indeterminate: false }
    } else {
      return { selected: false, indeterminate: true }
    }
  }

  // For leaf nodes (documents), check directly
  return {
    selected: selectedIds.has(node.dingtalk_node_id),
    indeterminate: false
  }
}

/**
 * Check if node matches search or has matching children
 */
function nodeMatchesSearch(node: DingtalkDocNode, searchValue: string): boolean {
  const lowerSearch = searchValue.toLowerCase()

  // Check if current node matches
  if (node.name.toLowerCase().includes(lowerSearch)) {
    return true
  }

  // Check if any child matches
  if (node.children) {
    return node.children.some(child => nodeMatchesSearch(child, searchValue))
  }

  return false
}

/**
 * Tree node component
 */
function TreeNode({
  node,
  level,
  selectedIds,
  expandedIds,
  onToggleExpand,
  onToggleSelect,
  searchValue,
}: TreeNodeProps) {
  const isFolder = node.node_type === 'folder'
  const isExpanded = expandedIds.has(node.dingtalk_node_id)
  const { selected, indeterminate } = getNodeSelectionState(node, selectedIds)

  // Filter by search
  const matchesSearch = useMemo(() => {
    if (!searchValue) return true
    return nodeMatchesSearch(node, searchValue)
  }, [node, searchValue])

  // Auto-expand if search matches children
  const shouldAutoExpand = useMemo(() => {
    if (!searchValue || !node.children) return false
    return node.children.some(child => nodeMatchesSearch(child, searchValue))
  }, [node.children, searchValue])

  const hasChildren = node.children && node.children.length > 0

  if (!matchesSearch) return null

  const handleCheckboxChange = (checked: boolean) => {
    onToggleSelect(node, checked)
  }

  return (
    <div>
      <div
        className={cn(
          'flex items-center gap-2 py-1.5 px-2 rounded-md text-sm transition-colors',
          'hover:bg-surface-hover',
          level === 0 && 'mt-0.5'
        )}
        style={{ paddingLeft: `${level * 20 + 8}px` }}
      >
        {/* Expand/collapse button */}
        {hasChildren ? (
          <button
            type="button"
            onClick={() => onToggleExpand(node.dingtalk_node_id)}
            className="flex-shrink-0 h-6 w-6 flex items-center justify-center rounded hover:bg-muted"
            data-testid={`dingtalk-expand-${node.dingtalk_node_id}`}
          >
            {isExpanded || shouldAutoExpand ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" />
            )}
          </button>
        ) : (
          <span className="flex-shrink-0 w-6" />
        )}

        {/* Checkbox */}
        <Checkbox
          checked={selected}
          indeterminate={indeterminate}
          onCheckedChange={handleCheckboxChange}
          className="flex-shrink-0"
          data-testid={`dingtalk-checkbox-${node.dingtalk_node_id}`}
        />

        {/* Icon */}
        {isFolder ? (
          isExpanded || shouldAutoExpand ? (
            <FolderOpen className="w-4 h-4 flex-shrink-0 text-primary" />
          ) : (
            <Folder className="w-4 h-4 flex-shrink-0 text-text-secondary" />
          )
        ) : (
          <FileText className="w-4 h-4 flex-shrink-0 text-text-secondary" />
        )}

        {/* Name */}
        <span
          className={cn(
            'flex-1 truncate',
            isFolder ? 'font-medium' : ''
          )}
          title={node.name}
        >
          {node.name}
        </span>
      </div>

      {/* Children */}
      {hasChildren && (isExpanded || shouldAutoExpand) && (
        <div>
          {node.children!.map(child => (
            <TreeNode
              key={child.dingtalk_node_id}
              node={child}
              level={level + 1}
              selectedIds={selectedIds}
              expandedIds={expandedIds}
              onToggleExpand={onToggleExpand}
              onToggleSelect={onToggleSelect}
              searchValue={searchValue}
            />
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Main component for DingTalk document selector
 */
export function DingtalkDocSelector({
  selectedContexts,
  onSelectionChange,
  searchValue = '',
}: DingtalkDocSelectorProps) {
  const { t } = useTranslation('knowledge')
  const [docTree, setDocTree] = useState<DingtalkDocNode[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  // Selected IDs set
  const selectedIds = useMemo(() => {
    return new Set(selectedContexts.map(ctx => ctx.dingtalk_node_id))
  }, [selectedContexts])

  // Load DingTalk document tree
  useEffect(() => {
    const loadDocs = async () => {
      setLoading(true)
      try {
        const response = await dingtalkDocApi.getDocs()
        setDocTree(response.nodes)
        // Expand first level by default
        const firstLevelIds = response.nodes.map(n => n.dingtalk_node_id)
        setExpandedIds(new Set(firstLevelIds))
      } catch (err) {
        console.error('Failed to load DingTalk docs:', err)
        setError(t('document.dingtalk.syncFailed'))
      } finally {
        setLoading(false)
      }
    }
    loadDocs()
  }, [t])

  // Toggle expand/collapse
  const handleToggleExpand = useCallback((nodeId: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(nodeId)) {
        next.delete(nodeId)
      } else {
        next.add(nodeId)
      }
      return next
    })
  }, [])

  // Convert node to context
  const nodeToContext = useCallback((node: DingtalkDocNode): DingtalkDocContext => ({
    id: `dingtalk-${node.dingtalk_node_id}`,
    name: node.name,
    type: 'dingtalk_doc',
    dingtalk_node_id: node.dingtalk_node_id,
    doc_url: node.doc_url,
    parent_node_id: node.parent_node_id,
    node_type: node.node_type,
    workspace_id: node.workspace_id,
  }), [])

  // Get all selectable document nodes (recursively)
  const getSelectableDocNodes = useCallback((node: DingtalkDocNode): DingtalkDocNode[] => {
    if (node.node_type !== 'folder') {
      return [node]
    }
    if (!node.children || node.children.length === 0) {
      return []
    }
    return node.children.flatMap(child => getSelectableDocNodes(child))
  }, [])

  // Handle selection toggle (cascade)
  const handleToggleSelect = useCallback((node: DingtalkDocNode, selected: boolean) => {
    const docNodes = getSelectableDocNodes(node)

    if (selected) {
      // Add all document nodes
      const newContexts = docNodes.map(nodeToContext)
      // Merge with existing selections, avoid duplicates
      const existingIds = new Set(selectedContexts.map(ctx => ctx.dingtalk_node_id))
      const uniqueNewContexts = newContexts.filter(ctx => !existingIds.has(ctx.dingtalk_node_id))
      onSelectionChange([...selectedContexts, ...uniqueNewContexts])
    } else {
      // Remove all related document nodes
      const docIdsToRemove = new Set(docNodes.map(n => n.dingtalk_node_id))
      onSelectionChange(
        selectedContexts.filter(ctx => !docIdsToRemove.has(ctx.dingtalk_node_id))
      )
    }
  }, [selectedContexts, onSelectionChange, nodeToContext, getSelectableDocNodes])

  // Count documents in tree
  const docCount = useMemo(() => {
    const countDocs = (nodes: DingtalkDocNode[]): number => {
      return nodes.reduce((count, node) => {
        if (node.node_type !== 'folder') {
          return count + 1
        }
        if (node.children) {
          return count + countDocs(node.children)
        }
        return count
      }, 0)
    }
    return countDocs(docTree)
  }, [docTree])

  if (loading) {
    return (
      <div className="py-8 text-center text-sm text-text-muted">
        {t('common:actions.loading')}
      </div>
    )
  }

  if (error) {
    return (
      <div className="py-4 px-3 text-center">
        <p className="text-sm text-red-500 mb-2">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="text-xs text-primary hover:underline"
        >
          {t('common:actions.retry')}
        </button>
      </div>
    )
  }

  if (docTree.length === 0) {
    return (
      <div className="py-6 px-4 text-center">
        <p className="text-sm text-text-muted mb-3">
          {t('document.dingtalk.emptyState')}
        </p>
        <p className="text-xs text-text-muted">
          {t('document.dingtalk.syncHint')}
        </p>
      </div>
    )
  }

  return (
    <div className="py-2" data-testid="dingtalk-doc-selector">
      {/* Stats */}
      <div className="px-3 pb-2 text-xs text-text-muted border-b border-border mb-2">
        {t('document.dingtalk.docCount', { count: docCount })} ·{' '}
        {t('dingtalk.selectedCount', { count: selectedContexts.length })}
      </div>

      {/* Tree list */}
      <div className="max-h-[280px] overflow-y-auto">
        {docTree.map(node => (
          <TreeNode
            key={node.dingtalk_node_id}
            node={node}
            level={0}
            selectedIds={selectedIds}
            expandedIds={expandedIds}
            onToggleExpand={handleToggleExpand}
            onToggleSelect={handleToggleSelect}
            searchValue={searchValue}
          />
        ))}
      </div>
    </div>
  )
}
