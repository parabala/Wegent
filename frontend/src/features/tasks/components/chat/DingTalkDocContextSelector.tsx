// SPDX-FileCopyrightText: 2025 Weibo, Inc.
//
// SPDX-License-Identifier: Apache-2.0

/**
 * DingTalkDocContextSelector - Tree-based DingTalk document selector for chat context.
 *
 * Renders the synced DingTalk document tree with checkboxes.
 * Selecting a folder automatically selects all its descendant nodes.
 * Supports three sections: "My Documents", "My Knowledge Base", and "Organization Knowledge Base".
 */

'use client'

import React, { useState, useCallback, useEffect, useMemo } from 'react'
import Link from 'next/link'
import {
  Folder,
  FolderOpen,
  ChevronRight,
  ChevronDown,
  FileText,
  RefreshCw,
  ExternalLink,
  Check,
  Minus,
  Search,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/hooks/useTranslation'
import { dingtalkDocApi } from '@/apis/dingtalk-doc'
import type { DingtalkDocNode } from '@/types/dingtalk-doc'
import type { DingTalkDocContext } from '@/types/context'

/** Collect all descendant node IDs (including self) from a node. */
export function collectDescendants(node: DingtalkDocNode): string[] {
  const ids: string[] = [node.dingtalk_node_id]
  if (node.children) {
    for (const child of node.children) {
      ids.push(...collectDescendants(child))
    }
  }
  return ids
}

/** Check if all nodes under a tree node are selected. */
export function isNodeFullySelected(
  node: DingtalkDocNode,
  selected: Set<string>
): boolean {
  if (!selected.has(node.dingtalk_node_id)) return false
  if (node.children) {
    return node.children.every(child => isNodeFullySelected(child, selected))
  }
  return true
}

/** Check if some (but not all) nodes under a tree node are selected. */
export function isNodePartiallySelected(
  node: DingtalkDocNode,
  selected: Set<string>
): boolean {
  const allIds = collectDescendants(node)
  const selectedCount = allIds.filter(id => selected.has(id)).length
  return selectedCount > 0 && selectedCount < allIds.length
}

interface TreeNodeItemProps {
  node: DingtalkDocNode
  level: number
  selectedIds: Set<string>
  onToggle: (node: DingtalkDocNode) => void
  searchQuery: string
}

/** Recursive tree node item with checkbox. */
export function DingtalkContextTreeNode({
  node,
  level,
  selectedIds,
  onToggle,
  searchQuery,
}: TreeNodeItemProps) {
  const isFolder = node.node_type === 'folder'
  const [isExpanded, setIsExpanded] = useState(level === 0)
  const isSelected = isFolder
    ? isNodeFullySelected(node, selectedIds)
    : selectedIds.has(node.dingtalk_node_id)
  const isPartial = isFolder
    ? isNodePartiallySelected(node, selectedIds)
    : false
  const hasChildren = isFolder && node.children && node.children.length > 0

  // Auto-expand when searching
  useEffect(() => {
    if (searchQuery) setIsExpanded(true)
  }, [searchQuery])

  const handleToggle = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setIsExpanded(prev => !prev)
  }, [])

  const handleCheck = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      onToggle(node)
    },
    [node, onToggle]
  )

  // Filter by search query
  const normalizedQuery = searchQuery.toLowerCase()
  const matchesSearch =
    !searchQuery || node.name.toLowerCase().includes(normalizedQuery)
  const hasDescendantMatch = (descendant: DingtalkDocNode): boolean => {
    if (descendant.name.toLowerCase().includes(normalizedQuery)) return true
    return descendant.children
      ? descendant.children.some(hasDescendantMatch)
      : false
  }
  const childrenMatchSearch =
    searchQuery && node.children?.some(hasDescendantMatch)

  if (!matchesSearch && !childrenMatchSearch && !isFolder) return null
  if (!matchesSearch && !childrenMatchSearch && isFolder) {
    // Still render folder if it has matching children
    const hasMatchingChildren = node.children?.some(child => {
      const allNames = [
        child.name,
        ...(child.children?.map(c => c.name) ?? []),
      ]
      return allNames.some(n =>
        n.toLowerCase().includes(searchQuery.toLowerCase())
      )
    })
    if (!hasMatchingChildren && searchQuery) return null
  }

  return (
    <div>
      <div
        className={cn(
          'flex items-center gap-1.5 py-1.5 rounded-md text-sm transition-colors cursor-pointer',
          'hover:bg-surface-hover group'
        )}
        style={{ paddingLeft: `${level * 16 + 8}px`, paddingRight: '8px' }}
        onClick={handleCheck}
        role="button"
        tabIndex={0}
        onKeyDown={e => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onToggle(node)
          }
        }}
        data-testid={`dingtalk-ctx-node-${node.dingtalk_node_id}`}
      >
        {/* Expand toggle for folders */}
        {isFolder && hasChildren ? (
          <button
            type="button"
            className="flex-shrink-0 w-5 h-5 flex items-center justify-center hover:bg-muted rounded"
            onClick={handleToggle}
            data-testid={`dingtalk-ctx-expand-${node.dingtalk_node_id}`}
          >
            {isExpanded ? (
              <ChevronDown className="w-3 h-3 text-text-muted" />
            ) : (
              <ChevronRight className="w-3 h-3 text-text-muted" />
            )}
          </button>
        ) : (
          <span className="flex-shrink-0 w-5 h-5" />
        )}

        {/* Checkbox */}
        <div
          className={cn(
            'flex-shrink-0 w-4 h-4 rounded border-[1.5px] flex items-center justify-center transition-colors',
            isSelected
              ? 'bg-primary border-primary'
              : isPartial
                ? 'bg-primary/20 border-primary'
                : 'border-border bg-base group-hover:border-primary/50'
          )}
        >
          {isSelected && <Check className="w-2.5 h-2.5 text-white stroke-[3]" />}
          {!isSelected && isPartial && (
            <Minus className="w-2.5 h-2.5 text-primary stroke-[3]" />
          )}
        </div>

        {/* Icon */}
        {isFolder ? (
          isExpanded ? (
            <FolderOpen className="w-3.5 h-3.5 flex-shrink-0 text-amber-500" />
          ) : (
            <Folder className="w-3.5 h-3.5 flex-shrink-0 text-amber-500" />
          )
        ) : (
          <FileText className="w-3.5 h-3.5 flex-shrink-0 text-text-muted" />
        )}

        {/* Name */}
        <span
          className="flex-1 truncate text-sm text-text-primary"
          title={node.name}
        >
          {node.name}
        </span>

        {/* External link for docs (visible on hover) */}
        {!isFolder && node.doc_url && (
          <a
            href={node.doc_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
            onClick={e => e.stopPropagation()}
            aria-label={node.name}
            data-testid={`dingtalk-ctx-link-${node.dingtalk_node_id}`}
          >
            <ExternalLink className="w-3 h-3 text-text-muted hover:text-primary" />
          </a>
        )}
      </div>

      {/* Children */}
      {isFolder && hasChildren && isExpanded && (
        <div>
          {node.children!.map(child => (
            <DingtalkContextTreeNode
              key={child.dingtalk_node_id}
              node={child}
              level={level + 1}
              selectedIds={selectedIds}
              onToggle={onToggle}
              searchQuery={searchQuery}
            />
          ))}
        </div>
      )}
    </div>
  )
}

type SectionKey = 'my-docs' | 'my-wikispace' | 'org-wikispace'

interface SectionState {
  nodes: DingtalkDocNode[]
  loading: boolean
  syncing: boolean
  error: string | null
  configured: boolean
  lastSyncedAt: string | null
}

function createEmptySectionState(
  configured: boolean = false
): SectionState {
  return {
    nodes: [],
    loading: false,
    syncing: false,
    error: null,
    configured,
    lastSyncedAt: null,
  }
}

interface DingTalkDocContextSelectorProps {
  selectedContexts: Set<string>
  onSelect: (context: DingTalkDocContext) => void
  onDeselect: (id: string) => void
  onSelectMultiple: (contexts: DingTalkDocContext[]) => void
  onDeselectMultiple: (ids: string[]) => void
}

/**
 * DingTalk document context selector panel.
 * Displays the synced document tree with checkboxes for multi-selection.
 * Supports three sections: My Documents, My Knowledge Base, Org Knowledge Base.
 */
export function DingTalkDocContextSelector({
  selectedContexts,
  onSelect,
  onDeselect,
  onSelectMultiple,
  onDeselectMultiple,
}: DingTalkDocContextSelectorProps) {
  const { t } = useTranslation('chat')

  const [activeSection, setActiveSection] = useState<SectionKey>('my-docs')

  // Per-section state
  const [myDocs, setMyDocs] = useState<SectionState>(
    createEmptySectionState(true)
  )
  const [myWikispace, setMyWikispace] = useState<SectionState>(
    createEmptySectionState(false)
  )
  const [orgWikispace, setOrgWikispace] = useState<SectionState>(
    createEmptySectionState(false)
  )

  // Shared search state
  const [searchQuery, setSearchQuery] = useState('')

  const getSection = useCallback(
    (section: SectionKey): SectionState => {
      switch (section) {
        case 'my-docs':
          return myDocs
        case 'my-wikispace':
          return myWikispace
        case 'org-wikispace':
          return orgWikispace
      }
    },
    [myDocs, myWikispace, orgWikispace]
  )

  const setSection = useCallback(
    (section: SectionKey, updater: (prev: SectionState) => SectionState) => {
      switch (section) {
        case 'my-docs':
          setMyDocs(updater)
          break
        case 'my-wikispace':
          setMyWikispace(updater)
          break
        case 'org-wikispace':
          setOrgWikispace(updater)
          break
      }
    },
    []
  )

  const fetchDocs = useCallback(async () => {
    setMyDocs(prev => ({ ...prev, loading: true, error: null }))
    try {
      const [tree, status] = await Promise.all([
        dingtalkDocApi.getDocs(),
        dingtalkDocApi.getSyncStatus(),
      ])
      setMyDocs(prev => ({
        ...prev,
        nodes: tree.nodes,
        loading: false,
        configured: status.is_configured,
        lastSyncedAt: status.last_synced_at,
      }))
    } catch (err) {
      console.error('Failed to fetch DingTalk docs:', err)
      setMyDocs(prev => ({
        ...prev,
        loading: false,
        error: t('chat:dingtalkDocs.loadFailed'),
      }))
    }
  }, [t])

  const fetchWikispace = useCallback(
    async (section: SectionKey) => {
      const wikiSpaceType =
        section === 'my-wikispace' ? 'mywikispace' : 'orgwikispace'
      const updater = section === 'my-wikispace' ? setMyWikispace : setOrgWikispace
      updater(prev => ({ ...prev, loading: true, error: null }))
      try {
        const [tree, status] = await Promise.all([
          dingtalkDocApi.getWikispaceNodes(wikiSpaceType),
          dingtalkDocApi.getWikispaceSyncStatus(wikiSpaceType),
        ])
        updater(prev => ({
          ...prev,
          nodes: tree.nodes,
          loading: false,
          configured: status.is_configured,
          lastSyncedAt: status.last_synced_at,
        }))
      } catch (err) {
        console.error(
          `Failed to fetch DingTalk wikispace (${wikiSpaceType}):`,
          err
        )
        updater(prev => ({
          ...prev,
          loading: false,
          error: t('chat:dingtalkDocs.loadFailed'),
        }))
      }
    },
    [t]
  )

  useEffect(() => {
    fetchDocs()
    fetchWikispace('my-wikispace')
    fetchWikispace('org-wikispace')
  }, [fetchDocs, fetchWikispace])

  const handleSync = useCallback(async () => {
    setMyDocs(prev => ({ ...prev, syncing: true, error: null }))
    try {
      await dingtalkDocApi.syncDocs()
      await fetchDocs()
    } catch (err) {
      console.error('Failed to sync DingTalk docs:', err)
      setMyDocs(prev => ({
        ...prev,
        syncing: false,
        error: t('chat:dingtalkDocs.syncFailed'),
      }))
    }
  }, [fetchDocs, t])

  const handleWikispaceSync = useCallback(async () => {
    // Syncs both types in one call
    setMyWikispace(prev => ({ ...prev, syncing: true, error: null }))
    setOrgWikispace(prev => ({ ...prev, syncing: true, error: null }))
    try {
      await dingtalkDocApi.syncWikispaceNodes()
      await Promise.all([
        fetchWikispace('my-wikispace'),
        fetchWikispace('org-wikispace'),
      ])
    } catch (err) {
      console.error('Failed to sync DingTalk wikispace:', err)
      setMyWikispace(prev => ({
        ...prev,
        syncing: false,
        error: t('chat:dingtalkDocs.syncFailed'),
      }))
      setOrgWikispace(prev => ({
        ...prev,
        syncing: false,
        error: t('chat:dingtalkDocs.syncFailed'),
      }))
    }
  }, [fetchWikispace, t])

  /** Build a DingTalkDocContext from a node. */
  const buildContext = useCallback(
    (node: DingtalkDocNode): DingTalkDocContext => {
      return {
        id: node.dingtalk_node_id,
        name: node.name,
        type: 'dingtalk_doc',
        doc_url: node.doc_url,
        node_type: node.node_type as 'folder' | 'doc' | 'file',
        dingtalk_node_id: node.dingtalk_node_id,
      }
    },
    []
  )

  /** Handle toggle for a single node (folder = select/deselect all descendants). */
  const handleToggle = useCallback(
    (node: DingtalkDocNode) => {
      if (node.node_type === 'folder') {
        // Collect all descendant IDs (including folder itself)
        const allIds = collectDescendants(node)
        const allSelected = allIds.every(id => selectedContexts.has(id))

        if (allSelected) {
          // Deselect all descendants
          onDeselectMultiple(allIds)
        } else {
          // Select all descendants not yet selected
          const toAdd: DingTalkDocContext[] = []
          const addNode = (n: DingtalkDocNode) => {
            if (!selectedContexts.has(n.dingtalk_node_id)) {
              toAdd.push(buildContext(n))
            }
            if (n.children) {
              n.children.forEach(addNode)
            }
          }
          addNode(node)
          if (toAdd.length > 0) {
            onSelectMultiple(toAdd)
          }
        }
      } else {
        // Single doc/file toggle
        if (selectedContexts.has(node.dingtalk_node_id)) {
          onDeselect(node.dingtalk_node_id)
        } else {
          onSelect(buildContext(node))
        }
      }
    },
    [selectedContexts, buildContext, onSelect, onDeselect, onSelectMultiple]
  )

  // Count of selected doc/file nodes across all sections
  const selectedDocCount = useMemo(() => {
    const countDocs = (nodeList: DingtalkDocNode[]): number => {
      let count = 0
      for (const node of nodeList) {
        if (
          node.node_type !== 'folder' &&
          selectedContexts.has(node.dingtalk_node_id)
        ) {
          count++
        }
        if (node.children) {
          count += countDocs(node.children)
        }
      }
      return count
    }
    return (
      countDocs(myDocs.nodes) +
      countDocs(myWikispace.nodes) +
      countDocs(orgWikispace.nodes)
    )
  }, [myDocs.nodes, myWikispace.nodes, orgWikispace.nodes, selectedContexts])

  // Derived active section values
  const activeState = getSection(activeSection)

  const handleActiveSync =
    activeSection === 'my-docs' ? handleSync : handleWikispaceSync
  const handleRetry =
    activeSection === 'my-docs'
      ? fetchDocs
      : () => fetchWikispace(activeSection)

  /** Render the content area for the active section. */
  const renderContent = () => {
    if (activeState.loading) {
      return (
        <div className="py-6 px-4 text-center text-sm text-text-muted">
          {t('common:actions.loading')}
        </div>
      )
    }

    if (activeSection === 'my-docs' && !myDocs.configured) {
      return (
        <div className="py-6 px-4 text-center space-y-3">
          <p className="text-sm text-text-muted">
            {t('chat:dingtalkDocs.notConfigured')}
          </p>
          <Link
            href="/settings/integrations"
            className="inline-flex items-center gap-1.5 text-sm text-primary hover:text-primary/80 font-medium transition-colors"
          >
            {t('chat:dingtalkDocs.goToConfigure')}
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        </div>
      )
    }

    if (activeState.error) {
      return (
        <div className="py-4 px-3 text-center space-y-2">
          <p className="text-sm text-red-500">{activeState.error}</p>
          <button
            onClick={handleRetry}
            className="text-xs text-primary hover:underline"
          >
            {t('common:actions.retry')}
          </button>
        </div>
      )
    }

    if (
      (activeSection === 'my-wikispace' && !myWikispace.configured) ||
      (activeSection === 'org-wikispace' && !orgWikispace.configured)
    ) {
      return (
        <div className="py-6 px-4 text-center space-y-3">
          <p className="text-sm text-text-muted">
            {t('chat:dingtalkDocs.wikispaceNotConfigured')}
          </p>
          <a
            href="/settings?section=integrations&tab=integrations"
            className="inline-flex items-center gap-1.5 text-sm text-primary hover:text-primary/80 font-medium transition-colors"
          >
            {t('chat:dingtalkDocs.goToConfigure')}
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      )
    }

    if (activeState.nodes.length === 0) {
      return (
        <div className="py-6 px-4 text-center space-y-3">
          <p className="text-sm text-text-muted">
            {t('chat:dingtalkDocs.empty')}
          </p>
          <button
            type="button"
            onClick={handleActiveSync}
            disabled={activeState.syncing}
            className="inline-flex items-center gap-1.5 text-sm text-primary hover:text-primary/80 font-medium transition-colors disabled:opacity-50"
          >
            <RefreshCw
              className={cn(
                'w-3.5 h-3.5',
                activeState.syncing && 'animate-spin'
              )}
            />
            {activeState.syncing
              ? t('chat:dingtalkDocs.syncing')
              : t('chat:dingtalkDocs.syncNow')}
          </button>
        </div>
      )
    }

    return activeState.nodes.map(node => (
      <DingtalkContextTreeNode
        key={node.dingtalk_node_id}
        node={node}
        level={0}
        selectedIds={selectedContexts}
        onToggle={handleToggle}
        searchQuery={searchQuery}
      />
    ))
  }

  return (
    <div className="flex flex-col min-h-0 flex-1">
      {/* Section switcher - always visible */}
      <div className="flex border-b border-border flex-shrink-0">
        <button
          type="button"
          onClick={() => setActiveSection('my-docs')}
          className={cn(
            'flex-1 py-1.5 text-xs font-medium transition-colors',
            activeSection === 'my-docs'
              ? 'text-text-primary border-b-2 border-primary'
              : 'text-text-muted hover:text-text-primary'
          )}
          data-testid="dingtalk-section-my-docs"
        >
          {t('chat:dingtalkDocs.myDocsTab')}
        </button>
        <button
          type="button"
          onClick={() => setActiveSection('my-wikispace')}
          className={cn(
            'flex-1 py-1.5 text-xs font-medium transition-colors',
            activeSection === 'my-wikispace'
              ? 'text-text-primary border-b-2 border-primary'
              : 'text-text-muted hover:text-text-primary'
          )}
          data-testid="dingtalk-section-my-wikispace"
        >
          {t('chat:dingtalkDocs.myWikispaceTab')}
        </button>
        <button
          type="button"
          onClick={() => setActiveSection('org-wikispace')}
          className={cn(
            'flex-1 py-1.5 text-xs font-medium transition-colors',
            activeSection === 'org-wikispace'
              ? 'text-text-primary border-b-2 border-primary'
              : 'text-text-muted hover:text-text-primary'
          )}
          data-testid="dingtalk-section-org-wikispace"
        >
          {t('chat:dingtalkDocs.orgWikispaceTab')}
        </button>
      </div>

      {/* Search input */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border flex-shrink-0">
        <Search className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          placeholder={t('chat:dingtalkDocs.searchPlaceholder')}
          className="flex-1 text-sm bg-transparent outline-none text-text-primary placeholder:text-text-muted"
          data-testid="dingtalk-search-input"
        />
      </div>

      {/* Sync toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border flex-shrink-0">
        <span className="text-xs text-text-muted">
          {activeState.lastSyncedAt
            ? t('chat:dingtalkDocs.lastSynced', {
                time: new Date(activeState.lastSyncedAt).toLocaleString(),
              })
            : t('chat:dingtalkDocs.neverSynced')}
          {selectedDocCount > 0 && (
            <span className="ml-2 text-primary font-medium">
              {t('chat:dingtalkDocs.selectedCount', {
                count: selectedDocCount,
              })}
            </span>
          )}
        </span>
        <button
          type="button"
          onClick={handleActiveSync}
          disabled={activeState.syncing}
          className={cn(
            'flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors',
            activeState.syncing && 'opacity-50 cursor-not-allowed'
          )}
          data-testid="dingtalk-sync-button"
        >
          <RefreshCw
            className={cn('w-3 h-3', activeState.syncing && 'animate-spin')}
          />
          {activeState.syncing
            ? t('chat:dingtalkDocs.syncing')
            : t('chat:dingtalkDocs.sync')}
        </button>
      </div>

      {/* Tree content area */}
      <div className="overflow-y-auto flex-1 max-h-[260px] py-1 px-1">
        {renderContent()}
      </div>
    </div>
  )
}

/**
 * Collect all DingTalk doc IDs from selected contexts.
 * Used by ContextSelector to bridge the generic ContextItem type to the
 * Set<string> format required by DingTalkDocContextSelector.
 */
export function getDingTalkSelectedIds(
  selectedContexts: { type: string; id: number | string }[]
): Set<string> {
  return new Set(
    selectedContexts
      .filter(ctx => ctx.type === 'dingtalk_doc')
      .map(ctx => String(ctx.id))
  )
}