// SPDX-FileCopyrightText: 2025 Weibo, Inc.
//
// SPDX-License-Identifier: Apache-2.0

/**
 * DingtalkDocsPage - Main page component for DingTalk document browsing.
 *
 * Layout: header with sync button + tabs for "My Documents", "My Knowledge Base", and "Org Knowledge Base".
 */

'use client'

import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, FolderOpen, BookOpen, Library, ExternalLink } from 'lucide-react'
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

interface DingtalkDocsPageProps {
  /** Whether DingTalk Docs MCP is configured for the user */
  isConfigured: boolean
  /** Whether DingTalk Wikispace MCP is configured for the user */
  isWikispaceConfigured?: boolean
  /** Callback when sync completes (to refresh sidebar count) */
  onSyncComplete?: () => void
}

export function DingtalkDocsPage({
  isConfigured,
  isWikispaceConfigured = false,
  onSyncComplete,
}: DingtalkDocsPageProps) {
  const { t } = useTranslation('knowledge')
  const [activeTab, setActiveTab] = useState<'my-docs' | 'my-wikispace' | 'org-wikispace'>('my-docs')

  // My Docs state
  const [docTree, setDocTree] = useState<DingtalkDocNode[]>([])
  const [docTotalCount, setDocTotalCount] = useState(0)
  const [docSyncStatus, setDocSyncStatus] = useState<DingtalkSyncStatus | null>(null)
  const [isLoadingDocs, setIsLoadingDocs] = useState(false)
  const [isSyncingDocs, setIsSyncingDocs] = useState(false)

  // My Wikispace state
  const [myWikispaceTree, setMyWikispaceTree] = useState<DingtalkDocNode[]>([])
  const [myWikispaceTotalCount, setMyWikispaceTotalCount] = useState(0)
  const [myWikispaceSyncStatus, setMyWikispaceSyncStatus] = useState<DingtalkSyncStatus | null>(null)
  const [isLoadingMyWikispace, setIsLoadingMyWikispace] = useState(false)
  const [isSyncingMyWikispace, setIsSyncingMyWikispace] = useState(false)

  // Org Wikispace state
  const [orgWikispaceTree, setOrgWikispaceTree] = useState<DingtalkDocNode[]>([])
  const [orgWikispaceTotalCount, setOrgWikispaceTotalCount] = useState(0)
  const [orgWikispaceSyncStatus, setOrgWikispaceSyncStatus] = useState<DingtalkSyncStatus | null>(null)
  const [isLoadingOrgWikispace, setIsLoadingOrgWikispace] = useState(false)
  const [isSyncingOrgWikispace, setIsSyncingOrgWikispace] = useState(false)

  // Load docs sync status on mount
  useEffect(() => {
    dingtalkDocApi
      .getSyncStatus()
      .then(setDocSyncStatus)
      .catch(() => {})
  }, [])

  // Load my wikispace sync status on mount
  useEffect(() => {
    if (isWikispaceConfigured) {
      dingtalkDocApi
        .getMyWikispaceSyncStatus()
        .then(setMyWikispaceSyncStatus)
        .catch(() => {})
    }
  }, [isWikispaceConfigured])

  // Load org wikispace sync status on mount
  useEffect(() => {
    if (isWikispaceConfigured) {
      dingtalkDocApi
        .getOrgWikispaceSyncStatus()
        .then(setOrgWikispaceSyncStatus)
        .catch(() => {})
    }
  }, [isWikispaceConfigured])

  // Load docs when status shows synced content
  useEffect(() => {
    if (docSyncStatus && docSyncStatus.total_nodes > 0) {
      loadDocs()
    }
  }, [docSyncStatus?.total_nodes]) // eslint-disable-line react-hooks/exhaustive-deps

  // Load my wikispace when status shows synced content
  useEffect(() => {
    if (myWikispaceSyncStatus && myWikispaceSyncStatus.total_nodes > 0) {
      loadMyWikispace()
    }
  }, [myWikispaceSyncStatus?.total_nodes]) // eslint-disable-line react-hooks/exhaustive-deps

  // Load org wikispace when status shows synced content
  useEffect(() => {
    if (orgWikispaceSyncStatus && orgWikispaceSyncStatus.total_nodes > 0) {
      loadOrgWikispace()
    }
  }, [orgWikispaceSyncStatus?.total_nodes]) // eslint-disable-line react-hooks/exhaustive-deps

  const loadDocs = useCallback(async () => {
    setIsLoadingDocs(true)
    try {
      const response = await dingtalkDocApi.getDocs()
      setDocTree(response.nodes)
      setDocTotalCount(response.total_count)
    } catch (error) {
      console.error('Failed to load DingTalk docs:', error)
    } finally {
      setIsLoadingDocs(false)
    }
  }, [])

  const loadMyWikispace = useCallback(async () => {
    setIsLoadingMyWikispace(true)
    try {
      const response = await dingtalkDocApi.getMyWikispaceNodes()
      setMyWikispaceTree(response.nodes)
      setMyWikispaceTotalCount(response.total_count)
    } catch (error) {
      console.error('Failed to load DingTalk my wikispace:', error)
    } finally {
      setIsLoadingMyWikispace(false)
    }
  }, [])

  const loadOrgWikispace = useCallback(async () => {
    setIsLoadingOrgWikispace(true)
    try {
      const response = await dingtalkDocApi.getOrgWikispaceNodes()
      setOrgWikispaceTree(response.nodes)
      setOrgWikispaceTotalCount(response.total_count)
    } catch (error) {
      console.error('Failed to load DingTalk org wikispace:', error)
    } finally {
      setIsLoadingOrgWikispace(false)
    }
  }, [])

  const handleSyncDocs = useCallback(async () => {
    setIsSyncingDocs(true)
    try {
      await dingtalkDocApi.syncDocs()
      const [docsResponse, status] = await Promise.all([
        dingtalkDocApi.getDocs(),
        dingtalkDocApi.getSyncStatus(),
      ])
      setDocTree(docsResponse.nodes)
      setDocTotalCount(docsResponse.total_count)
      setDocSyncStatus(status)
      onSyncComplete?.()
    } catch (error) {
      console.error('Failed to sync DingTalk docs:', error)
    } finally {
      setIsSyncingDocs(false)
    }
  }, [onSyncComplete])

  const handleSyncMyWikispace = useCallback(async () => {
    setIsSyncingMyWikispace(true)
    try {
      await dingtalkDocApi.syncMyWikispaceNodes()
      const [wsResponse, status] = await Promise.all([
        dingtalkDocApi.getMyWikispaceNodes(),
        dingtalkDocApi.getMyWikispaceSyncStatus(),
      ])
      setMyWikispaceTree(wsResponse.nodes)
      setMyWikispaceTotalCount(wsResponse.total_count)
      setMyWikispaceSyncStatus(status)
      onSyncComplete?.()
    } catch (error) {
      console.error('Failed to sync DingTalk my wikispace:', error)
    } finally {
      setIsSyncingMyWikispace(false)
    }
  }, [onSyncComplete])

  const handleSyncOrgWikispace = useCallback(async () => {
    setIsSyncingOrgWikispace(true)
    try {
      await dingtalkDocApi.syncOrgWikispaceNodes()
      const [wsResponse, status] = await Promise.all([
        dingtalkDocApi.getOrgWikispaceNodes(),
        dingtalkDocApi.getOrgWikispaceSyncStatus(),
      ])
      setOrgWikispaceTree(wsResponse.nodes)
      setOrgWikispaceTotalCount(wsResponse.total_count)
      setOrgWikispaceSyncStatus(status)
      onSyncComplete?.()
    } catch (error) {
      console.error('Failed to sync DingTalk org wikispace:', error)
    } finally {
      setIsSyncingOrgWikispace(false)
    }
  }, [onSyncComplete])

  const isSyncing =
    activeTab === 'my-docs'
      ? isSyncingDocs
      : activeTab === 'my-wikispace'
        ? isSyncingMyWikispace
        : isSyncingOrgWikispace
  const handleSync =
    activeTab === 'my-docs'
      ? handleSyncDocs
      : activeTab === 'my-wikispace'
        ? handleSyncMyWikispace
        : handleSyncOrgWikispace
  const activeSyncStatus =
    activeTab === 'my-docs'
      ? docSyncStatus
      : activeTab === 'my-wikispace'
        ? myWikispaceSyncStatus
        : orgWikispaceSyncStatus

  if (!isConfigured && !isWikispaceConfigured) {
    return <DingtalkNotConfigured />
  }

  return (
    <div className="flex flex-col h-full" data-testid="dingtalk-docs-page">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div className="flex items-center gap-3">
          <FolderOpen className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold text-text-primary">
            {t('document.sidebar.dingtalk', '钉钉文档')}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {activeSyncStatus?.last_synced_at && (
            <span className="text-xs text-text-muted">
              {t('document.dingtalk.lastSynced', '上次同步')}:{' '}
              {formatDateTime(new Date(activeSyncStatus.last_synced_at).getTime())}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleSync}
            disabled={
              isSyncing ||
              (activeTab === 'my-docs' ? !isConfigured : !isWikispaceConfigured)
            }
            className="h-11 min-w-[44px]"
            data-testid="dingtalk-sync-button"
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
      </div>

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onValueChange={v =>
          setActiveTab(v as 'my-docs' | 'my-wikispace' | 'org-wikispace')
        }
        className="flex flex-col flex-1 min-h-0"
      >
        <TabsList className="mx-6 mt-3 self-start rounded-md">
          <TabsTrigger value="my-docs" data-testid="dingtalk-tab-my-docs">
            <FolderOpen className="w-3.5 h-3.5 mr-1.5" />
            {t('document.dingtalk.myDocs', '我的文档')}
            {docTotalCount > 0 && (
              <span className="ml-1.5 text-xs text-text-muted">({docTotalCount})</span>
            )}
          </TabsTrigger>
          <TabsTrigger value="my-wikispace" data-testid="dingtalk-tab-my-wikispace">
            <BookOpen className="w-3.5 h-3.5 mr-1.5" />
            {t('document.dingtalk.myWikispace', '我的知识库')}
            {myWikispaceTotalCount > 0 && (
              <span className="ml-1.5 text-xs text-text-muted">({myWikispaceTotalCount})</span>
            )}
          </TabsTrigger>
          <TabsTrigger value="org-wikispace" data-testid="dingtalk-tab-org-wikispace">
            <Library className="w-3.5 h-3.5 mr-1.5" />
            {t('document.dingtalk.orgWikispace', '组织知识库')}
            {orgWikispaceTotalCount > 0 && (
              <span className="ml-1.5 text-xs text-text-muted">({orgWikispaceTotalCount})</span>
            )}
          </TabsTrigger>
        </TabsList>

        {/* My Docs tab */}
        <TabsContent value="my-docs" className="flex-1 flex flex-col min-h-0 mt-3">
          {!isConfigured ? (
            <DingtalkNotConfigured />
          ) : isLoadingDocs ? (
            <div className="flex-1 flex items-center justify-center">
              <Spinner size="lg" />
            </div>
          ) : docTotalCount === 0 ? (
            <DingtalkEmptyState
              onSync={handleSyncDocs}
              isSyncing={isSyncingDocs}
              hint={t('document.dingtalk.syncHint', '点击同步按钮从钉钉拉取文档列表')}
              t={t}
            />
          ) : (
            <div className="flex-1 overflow-y-auto custom-scrollbar">
              <DingtalkDocTreeView nodes={docTree} />
            </div>
          )}
        </TabsContent>

        {/* My Wikispace tab */}
        <TabsContent value="my-wikispace" className="flex-1 flex flex-col min-h-0 mt-3">
          {!isWikispaceConfigured ? (
            <WikispaceNotConfigured t={t} />
          ) : isLoadingMyWikispace ? (
            <div className="flex-1 flex items-center justify-center">
              <Spinner size="lg" />
            </div>
          ) : myWikispaceTotalCount === 0 ? (
            <DingtalkEmptyState
              onSync={handleSyncMyWikispace}
              isSyncing={isSyncingMyWikispace}
              hint={t('document.dingtalk.myWikispaceSyncHint', '点击同步按钮从钉钉拉取我的知识库')}
              t={t}
            />
          ) : (
            <div className="flex-1 overflow-y-auto custom-scrollbar">
              <DingtalkDocTreeView nodes={myWikispaceTree} />
            </div>
          )}
        </TabsContent>

        {/* Org Wikispace tab */}
        <TabsContent value="org-wikispace" className="flex-1 flex flex-col min-h-0 mt-3">
          {!isWikispaceConfigured ? (
            <WikispaceNotConfigured t={t} />
          ) : isLoadingOrgWikispace ? (
            <div className="flex-1 flex items-center justify-center">
              <Spinner size="lg" />
            </div>
          ) : orgWikispaceTotalCount === 0 ? (
            <DingtalkEmptyState
              onSync={handleSyncOrgWikispace}
              isSyncing={isSyncingOrgWikispace}
              hint={t('document.dingtalk.orgWikispaceSyncHint', '点击同步按钮从钉钉拉取组织知识库')}
              t={t}
            />
          ) : (
            <div className="flex-1 overflow-y-auto custom-scrollbar">
              <DingtalkDocTreeView nodes={orgWikispaceTree} />
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

/** Shared empty state component used by both tabs. */
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
      <Button variant="primary" onClick={onSync} disabled={isSyncing} className="h-11 min-w-[44px]">
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

/** Shown in wikispace tab when wikispace MCP is not configured. */
function WikispaceNotConfigured({ t }: { t: TFunction }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
      <BookOpen className="w-16 h-16 text-text-muted mb-4" />
      <h3 className="text-lg font-medium text-text-primary mb-2">
        {t('document.dingtalk.wikispaceNotConfigured', '钉钉知识库 MCP 未配置')}
      </h3>
      <p className="text-sm text-text-muted mb-4">
        {t('document.dingtalk.wikispaceConfigureHint', '请前往设置配置钉钉知识库 MCP')}
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
