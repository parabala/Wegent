// SPDX-FileCopyrightText: 2025 Weibo, Inc.
//
// SPDX-License-Identifier: Apache-2.0

/**
 * DingtalkDocsPage - Main page component for DingTalk document browsing.
 *
 * Layout: header with sync button + tabs for "My Documents", "My Knowledge Base",
 * and "Organization Knowledge Base".
 */

'use client'

import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, FolderOpen, BookOpen, Building2, ExternalLink } from 'lucide-react'
import type { TFunction } from 'i18next'
import { useTranslation } from '@/hooks/useTranslation'
import { formatDateTime } from '@/utils/dateTime'
import { dingtalkDocApi } from '@/apis/dingtalk-doc'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { DingtalkDocTreeView } from './DingtalkDocTreeView'
import { DingtalkNotConfigured } from './dingtalk-not-configured'
import type { DingtalkDocNode, DingtalkSyncStatus } from '@/types/dingtalk-doc'

type TabKey = 'my-docs' | 'my-wikispace' | 'org-wikispace'

interface DingtalkDocsPageProps {
  /** Whether DingTalk Docs MCP is configured for the user */
  isConfigured: boolean
  /** Whether DingTalk Wikispace MCP is configured for the user */
  isWikispaceConfigured?: boolean
  /** Callback when sync completes (to refresh sidebar count) */
  onSyncComplete?: () => void
}

interface TabState {
  tree: DingtalkDocNode[]
  totalCount: number
  syncStatus: DingtalkSyncStatus | null
  isLoading: boolean
  isSyncing: boolean
}

function createEmptyTabState(): TabState {
  return {
    tree: [],
    totalCount: 0,
    syncStatus: null,
    isLoading: false,
    isSyncing: false,
  }
}

export function DingtalkDocsPage({
  isConfigured,
  isWikispaceConfigured = false,
  onSyncComplete,
}: DingtalkDocsPageProps) {
  const { t } = useTranslation('knowledge')
  const [activeTab, setActiveTab] = useState<TabKey>('my-docs')

  // Per-tab state
  const [myDocs, setMyDocs] = useState<TabState>(createEmptyTabState)
  const [myWikispace, setMyWikispace] = useState<TabState>(createEmptyTabState)
  const [orgWikispace, setOrgWikispace] = useState<TabState>(createEmptyTabState)

  const getTabState = useCallback(
    (tab: TabKey): TabState => {
      switch (tab) {
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

  const setTabState = useCallback(
    (tab: TabKey, updater: (prev: TabState) => TabState) => {
      switch (tab) {
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

  // Load my-docs sync status on mount
  useEffect(() => {
    dingtalkDocApi
      .getSyncStatus()
      .then(status =>
        setMyDocs(prev => ({ ...prev, syncStatus: status }))
      )
      .catch(() => {})
  }, [])

  // Load wikispace sync statuses on mount
  useEffect(() => {
    if (isWikispaceConfigured) {
      dingtalkDocApi
        .getWikispaceSyncStatus('mywikispace')
        .then(status =>
          setMyWikispace(prev => ({ ...prev, syncStatus: status }))
        )
        .catch(() => {})
      dingtalkDocApi
        .getWikispaceSyncStatus('orgwikispace')
        .then(status =>
          setOrgWikispace(prev => ({ ...prev, syncStatus: status }))
        )
        .catch(() => {})
    }
  }, [isWikispaceConfigured])

  // Load my-docs when status shows synced content
  useEffect(() => {
    if (myDocs.syncStatus && myDocs.syncStatus.total_nodes > 0) {
      loadTab('my-docs')
    }
  }, [myDocs.syncStatus?.total_nodes]) // eslint-disable-line react-hooks/exhaustive-deps

  // Load my-wikispace when status shows synced content
  useEffect(() => {
    if (myWikispace.syncStatus && myWikispace.syncStatus.total_nodes > 0) {
      loadTab('my-wikispace')
    }
  }, [myWikispace.syncStatus?.total_nodes]) // eslint-disable-line react-hooks/exhaustive-deps

  // Load org-wikispace when status shows synced content
  useEffect(() => {
    if (orgWikispace.syncStatus && orgWikispace.syncStatus.total_nodes > 0) {
      loadTab('org-wikispace')
    }
  }, [orgWikispace.syncStatus?.total_nodes]) // eslint-disable-line react-hooks/exhaustive-deps

  const loadTab = useCallback(
    async (tab: TabKey) => {
      setTabState(tab, prev => ({ ...prev, isLoading: true }))
      try {
        let response: { nodes: DingtalkDocNode[]; total_count: number }
        if (tab === 'my-docs') {
          response = await dingtalkDocApi.getDocs()
        } else if (tab === 'my-wikispace') {
          response = await dingtalkDocApi.getWikispaceNodes('mywikispace')
        } else {
          response = await dingtalkDocApi.getWikispaceNodes('orgwikispace')
        }
        setTabState(tab, prev => ({
          ...prev,
          tree: response.nodes,
          totalCount: response.total_count,
          isLoading: false,
        }))
      } catch (error) {
        console.error(`Failed to load DingTalk ${tab}:`, error)
        setTabState(tab, prev => ({ ...prev, isLoading: false }))
      }
    },
    [setTabState]
  )

  const handleSync = useCallback(
    async (tab: TabKey) => {
      setTabState(tab, prev => ({ ...prev, isSyncing: true }))
      try {
        if (tab === 'my-docs') {
          await dingtalkDocApi.syncDocs()
          const [docsResponse, status] = await Promise.all([
            dingtalkDocApi.getDocs(),
            dingtalkDocApi.getSyncStatus(),
          ])
          setMyDocs(prev => ({
            ...prev,
            tree: docsResponse.nodes,
            totalCount: docsResponse.total_count,
            syncStatus: status,
            isSyncing: false,
          }))
        } else {
          // Sync wikispace (syncs both types at once)
          await dingtalkDocApi.syncWikispaceNodes()
          const wikiSpaceType =
            tab === 'my-wikispace' ? 'mywikispace' : 'orgwikispace'
          const updater =
            tab === 'my-wikispace' ? setMyWikispace : setOrgWikispace
          const [wsResponse, status] = await Promise.all([
            dingtalkDocApi.getWikispaceNodes(wikiSpaceType),
            dingtalkDocApi.getWikispaceSyncStatus(wikiSpaceType),
          ])
          updater(prev => ({
            ...prev,
            tree: wsResponse.nodes,
            totalCount: wsResponse.total_count,
            syncStatus: status,
            isSyncing: false,
          }))
        }
        onSyncComplete?.()
      } catch (error) {
        console.error(`Failed to sync DingTalk ${tab}:`, error)
        setTabState(tab, prev => ({ ...prev, isSyncing: false }))
      }
    },
    [setTabState, onSyncComplete]
  )

  const tabState = getTabState(activeTab)

  if (!isConfigured && !isWikispaceConfigured) {
    return <DingtalkNotConfigured />
  }

  return (
    <div className="flex flex-col flex-1 min-h-0" data-testid="dingtalk-docs-page">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div className="flex items-center gap-3">
          <FolderOpen className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold text-text-primary">
            {t('document.sidebar.dingtalk', '钉钉文档')}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {tabState.syncStatus?.last_synced_at && (
            <span className="text-xs text-text-muted">
              {t('document.dingtalk.lastSynced', '上次同步')}:{' '}
              {formatDateTime(
                new Date(tabState.syncStatus.last_synced_at).getTime()
              )}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleSync(activeTab)}
            disabled={
              tabState.isSyncing ||
              (activeTab === 'my-docs' ? !isConfigured : !isWikispaceConfigured)
            }
            className="h-11 min-w-[44px]"
            data-testid="dingtalk-sync-button"
          >
            {tabState.isSyncing ? (
              <>
                <Spinner size="sm" className="mr-1" />
                {t('document.dingtalk.syncing', '同步中...')}
              </>
            ) : (
              <>
                <RefreshCw className="w-3.5 h-3.5 mr-1" />
                {t('document.dingtalk.sync', '同步')}
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onValueChange={v => setActiveTab(v as TabKey)}
        className="flex flex-col flex-1 min-h-0"
      >
        <TabsList className="mx-6 mt-3 self-start rounded-md">
          <TabsTrigger value="my-docs" data-testid="dingtalk-tab-my-docs">
            <FolderOpen className="w-3.5 h-3.5 mr-1.5" />
            {t('document.dingtalk.myDocs', '我的文档')}
            {myDocs.totalCount > 0 && (
              <span className="ml-1.5 text-xs text-text-muted">
                ({myDocs.totalCount})
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger
            value="my-wikispace"
            data-testid="dingtalk-tab-my-wikispace"
          >
            <BookOpen className="w-3.5 h-3.5 mr-1.5" />
            {t('document.dingtalk.myWikispace', '我的知识库')}
            {myWikispace.totalCount > 0 && (
              <span className="ml-1.5 text-xs text-text-muted">
                ({myWikispace.totalCount})
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger
            value="org-wikispace"
            data-testid="dingtalk-tab-org-wikispace"
          >
            <Building2 className="w-3.5 h-3.5 mr-1.5" />
            {t('document.dingtalk.orgWikispace', '组织知识库')}
            {orgWikispace.totalCount > 0 && (
              <span className="ml-1.5 text-xs text-text-muted">
                ({orgWikispace.totalCount})
              </span>
            )}
          </TabsTrigger>
        </TabsList>

        {/* My Docs tab */}
        <TabsContent
          value="my-docs"
          className="flex-1 flex flex-col min-h-0 mt-3"
        >
          {!isConfigured ? (
            <DingtalkNotConfigured />
          ) : myDocs.isLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <Spinner size="lg" />
            </div>
          ) : myDocs.totalCount === 0 ? (
            <DingtalkEmptyState
              onSync={() => handleSync('my-docs')}
              isSyncing={myDocs.isSyncing}
              hint={t(
                'document.dingtalk.syncHint',
                '点击同步按钮从钉钉拉取文档列表'
              )}
              t={t}
            />
          ) : (
            <div className="flex-1 overflow-y-auto custom-scrollbar">
              <DingtalkDocTreeView nodes={myDocs.tree} />
            </div>
          )}
        </TabsContent>

        {/* My Wikispace tab */}
        <TabsContent
          value="my-wikispace"
          className="flex-1 flex flex-col min-h-0 mt-3"
        >
          {!isWikispaceConfigured ? (
            <WikispaceNotConfigured t={t} />
          ) : myWikispace.isLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <Spinner size="lg" />
            </div>
          ) : myWikispace.totalCount === 0 ? (
            <DingtalkEmptyState
              onSync={() => handleSync('my-wikispace')}
              isSyncing={myWikispace.isSyncing}
              hint={t(
                'document.dingtalk.wikispaceSyncHint',
                '点击同步按钮从钉钉拉取知识库'
              )}
              t={t}
            />
          ) : (
            <div className="flex-1 overflow-y-auto custom-scrollbar">
              <DingtalkDocTreeView nodes={myWikispace.tree} />
            </div>
          )}
        </TabsContent>

        {/* Org Wikispace tab */}
        <TabsContent
          value="org-wikispace"
          className="flex-1 flex flex-col min-h-0 mt-3"
        >
          {!isWikispaceConfigured ? (
            <WikispaceNotConfigured t={t} />
          ) : orgWikispace.isLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <Spinner size="lg" />
            </div>
          ) : orgWikispace.totalCount === 0 ? (
            <DingtalkEmptyState
              onSync={() => handleSync('org-wikispace')}
              isSyncing={orgWikispace.isSyncing}
              hint={t(
                'document.dingtalk.wikispaceSyncHint',
                '点击同步按钮从钉钉拉取知识库'
              )}
              t={t}
            />
          ) : (
            <div className="flex-1 overflow-y-auto custom-scrollbar">
              <DingtalkDocTreeView nodes={orgWikispace.tree} />
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

/** Shared empty state component used by all tabs. */
function DingtalkEmptyState({
  onSync,
  isSyncing,
  hint,
  t,
}: {
  onSync: () => void
  isSyncing: boolean
  hint: string
  t: TFunction
}) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
      <FolderOpen className="w-16 h-16 text-text-muted mb-4" />
      <h3 className="text-lg font-medium text-text-primary mb-2">
        {t('document.dingtalk.emptyState', '暂无文档')}
      </h3>
      <p className="text-sm text-text-muted mb-4">{hint}</p>
      <Button
        variant="primary"
        onClick={onSync}
        disabled={isSyncing}
        className="h-11 min-w-[44px]"
      >
        {isSyncing ? (
          <>
            <Spinner size="sm" className="mr-1" />
            {t('document.dingtalk.syncing', '同步中...')}
          </>
        ) : (
          <>
            <RefreshCw className="w-3.5 h-3.5 mr-1" />
            {t('document.dingtalk.sync', '同步')}
          </>
        )}
      </Button>
    </div>
  )
}

/** Shown in wikispace tabs when wikispace MCP is not configured. */
function WikispaceNotConfigured({ t }: { t: TFunction }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
      <BookOpen className="w-16 h-16 text-text-muted mb-4" />
      <h3 className="text-lg font-medium text-text-primary mb-2">
        {t(
          'document.dingtalk.wikispaceNotConfigured',
          '钉钉知识库 MCP 未配置'
        )}
      </h3>
      <p className="text-sm text-text-muted mb-4">
        {t(
          'document.dingtalk.wikispaceConfigureHint',
          '请前往设置配置钉钉知识库 MCP'
        )}
      </p>
      <a
        href="/settings?section=integrations&tab=integrations"
        className="inline-flex items-center gap-1.5 text-sm text-primary hover:text-primary/80 font-medium transition-colors"
      >
        {t('document.dingtalk.goToSettings', '前往设置')}
        <ExternalLink className="w-3.5 h-3.5" />
      </a>
    </div>
  )
}