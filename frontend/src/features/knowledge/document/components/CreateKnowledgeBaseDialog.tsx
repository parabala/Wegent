// SPDX-FileCopyrightText: 2025 Weibo, Inc.
//
// SPDX-License-Identifier: Apache-2.0

'use client'

import { useState, useEffect, useCallback } from 'react'
import { BookOpen, FolderOpen, Users } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { useTranslation } from '@/hooks/useTranslation'
import type { SummaryModelRef, KnowledgeBaseType, RetrievalConfig } from '@/types/knowledge'
import type { Group } from '@/types/group'
import { KnowledgeBaseForm } from './KnowledgeBaseForm'
import { knowledgeBaseApi } from '@/apis/knowledge-base'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface CreateKnowledgeBaseDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: {
    name: string
    description?: string
    retrieval_config?: Partial<RetrievalConfig>
    summary_enabled?: boolean
    summary_model_ref?: SummaryModelRef | null
    max_calls_per_conversation: number
    exempt_calls_before_check: number
    linked_group?: string | null
  }) => Promise<void>
  loading?: boolean
  scope?: 'personal' | 'group' | 'organization' | 'all'
  groupName?: string
  /** Knowledge base type selected from dropdown menu (read-only in dialog) */
  kbType?: KnowledgeBaseType
  /** Optional team ID for reading cached model preference */
  knowledgeDefaultTeamId?: number | null
  /** Whether to show group selector (for personal/organization scope) */
  showGroupSelector?: boolean
  /** Pre-selected group name (when creating from group page) */
  preSelectedGroup?: string | null
}

export function CreateKnowledgeBaseDialog({
  open,
  onOpenChange,
  onSubmit,
  loading,
  scope,
  groupName,
  kbType = 'notebook',
  knowledgeDefaultTeamId,
  showGroupSelector = false,
  preSelectedGroup = null,
}: CreateKnowledgeBaseDialogProps) {
  const { t } = useTranslation('knowledge')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  // Default enable summary for notebook type, disable for classic type
  const [summaryEnabled, setSummaryEnabled] = useState(kbType === 'notebook')
  const [summaryModelRef, setSummaryModelRef] = useState<SummaryModelRef | null>(null)
  const [summaryModelError, setSummaryModelError] = useState('')
  const [retrievalConfig, setRetrievalConfig] = useState<Partial<RetrievalConfig>>({
    retrieval_mode: 'vector',
    top_k: 5,
    score_threshold: 0.5,
    hybrid_weights: {
      vector_weight: 0.7,
      keyword_weight: 0.3,
    },
  })
  const [error, setError] = useState('')
  const [accordionValue, setAccordionValue] = useState<string>('')
  const [maxCalls, setMaxCalls] = useState(10)
  const [exemptCalls, setExemptCalls] = useState(5)

  // Group selector state
  const [manageableGroups, setManageableGroups] = useState<Group[]>([])
  const [selectedGroup, setSelectedGroup] = useState<string | null>(preSelectedGroup)
  const [loadingGroups, setLoadingGroups] = useState(false)

  // Load manageable groups function
  const loadManageableGroups = useCallback(async () => {
    setLoadingGroups(true)
    try {
      const response = await knowledgeBaseApi.getManageableGroups()
      setManageableGroups(response.items || [])
    } catch (err) {
      console.error('Failed to load manageable groups:', err)
    } finally {
      setLoadingGroups(false)
    }
  }, [])

  // Load manageable groups when dialog opens and group selector is enabled
  useEffect(() => {
    if (open && showGroupSelector) {
      loadManageableGroups()
    }
  }, [open, showGroupSelector, loadManageableGroups])

  // Update selected group when preSelectedGroup changes
  useEffect(() => {
    setSelectedGroup(preSelectedGroup)
  }, [preSelectedGroup])

  // Reset summaryEnabled when dialog opens based on kbType
  // This is necessary because useState initial value only applies on first mount,
  // but the dialog component persists and kbType can change between opens
  useEffect(() => {
    if (open) {
      setSummaryEnabled(kbType === 'notebook')
    }
  }, [open, kbType])

  // Auto-generate name when group is selected and name is empty
  const handleGroupChange = useCallback(
    (groupNameValue: string | null) => {
      setSelectedGroup(groupNameValue)

      // Auto-generate default name if name is empty and group is selected
      if (groupNameValue && !name.trim()) {
        const group = manageableGroups.find(g => g.name === groupNameValue)
        if (group) {
          const groupDisplayName = group.display_name || group.name
          setName(`${groupDisplayName} ${t('knowledge:document.knowledgeBase.defaultNameSuffix')}`)
        }
      }
    },
    [name, manageableGroups, t]
  )

  // Note: Auto-selection of retriever and embedding model is handled by RetrievalSettingsSection

  const handleSubmit = async () => {
    setError('')
    setSummaryModelError('')

    if (!name.trim()) {
      setError(t('knowledge:document.knowledgeBase.nameRequired'))
      return
    }

    if (name.length > 100) {
      setError(t('knowledge:document.knowledgeBase.nameTooLong'))
      return
    }

    // Validate summary model when summary is enabled
    if (summaryEnabled && !summaryModelRef) {
      setSummaryModelError(t('knowledge:document.summary.modelRequired'))
      return
    }

    // Validate call limits
    if (exemptCalls >= maxCalls) {
      setError(t('knowledge:document.callLimits.validationError'))
      setAccordionValue('advanced')
      return
    }

    // Note: retrieval_config is now optional - users can create KB without RAG
    // AI will use kb_ls/kb_head tools to explore documents instead of RAG search

    try {
      // Convert empty string to null for linked_group
      const linkedGroupValue = selectedGroup?.trim() || null
      await onSubmit({
        name: name.trim(),
        description: description.trim() || undefined,
        retrieval_config: retrievalConfig,
        summary_enabled: summaryEnabled,
        summary_model_ref: summaryEnabled ? summaryModelRef : null,
        max_calls_per_conversation: maxCalls,
        exempt_calls_before_check: exemptCalls,
        linked_group: linkedGroupValue,
      })
      // Reset form
      setName('')
      setDescription('')
      setSummaryEnabled(kbType === 'notebook')
      setSummaryModelRef(null)
      setRetrievalConfig({
        retrieval_mode: 'vector',
        top_k: 5,
        score_threshold: 0.5,
        hybrid_weights: {
          vector_weight: 0.7,
          keyword_weight: 0.3,
        },
      })
      setMaxCalls(10)
      setExemptCalls(5)
      setSelectedGroup(preSelectedGroup)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common:error'))
    }
  }

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      setName('')
      setDescription('')
      setSummaryEnabled(kbType === 'notebook')
      setSummaryModelRef(null)
      setSummaryModelError('')
      setRetrievalConfig({
        retrieval_mode: 'vector',
        top_k: 5,
        score_threshold: 0.5,
        hybrid_weights: {
          vector_weight: 0.7,
          keyword_weight: 0.3,
        },
      })
      setMaxCalls(10)
      setExemptCalls(5)
      setError('')
      setAccordionValue('')
      setSelectedGroup(preSelectedGroup)
    }
    onOpenChange(newOpen)
  }

  // Determine if this is a notebook type
  const isNotebook = kbType === 'notebook'

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>{t('knowledge:document.knowledgeBase.create')}</DialogTitle>
        </DialogHeader>
        <div className="flex-1 overflow-y-auto space-y-4 py-4">
          <KnowledgeBaseForm
            typeSection={
              <div className="space-y-2">
                <Label>{t('knowledge:document.knowledgeBase.type')}</Label>
                <div
                  className={`flex items-center gap-3 p-3 rounded-md border ${
                    isNotebook ? 'bg-primary/5 border-primary/20' : 'bg-muted border-border'
                  }`}
                >
                  <div
                    className={`flex-shrink-0 w-8 h-8 rounded-md flex items-center justify-center ${
                      isNotebook ? 'bg-primary/10 text-primary' : 'bg-surface text-text-secondary'
                    }`}
                  >
                    {isNotebook ? (
                      <BookOpen className="w-4 h-4" />
                    ) : (
                      <FolderOpen className="w-4 h-4" />
                    )}
                  </div>
                  <div>
                    <div className="font-medium text-sm">
                      {isNotebook
                        ? t('knowledge:document.knowledgeBase.typeNotebook')
                        : t('knowledge:document.knowledgeBase.typeClassic')}
                    </div>
                    <div className="text-xs text-text-muted">
                      {isNotebook
                        ? t('knowledge:document.knowledgeBase.notebookDesc')
                        : t('knowledge:document.knowledgeBase.classicDesc')}
                    </div>
                  </div>
                </div>
              </div>
            }
            name={name}
            description={description}
            onNameChange={value => setName(value)}
            onDescriptionChange={value => setDescription(value)}
            summaryEnabled={summaryEnabled}
            onSummaryEnabledChange={checked => {
              setSummaryEnabled(checked)
              if (!checked) {
                setSummaryModelRef(null)
                setSummaryModelError('')
              }
            }}
            summaryModelRef={summaryModelRef}
            summaryModelError={summaryModelError}
            onSummaryModelChange={value => {
              setSummaryModelRef(value)
              setSummaryModelError('')
            }}
            knowledgeDefaultTeamId={knowledgeDefaultTeamId}
            callLimits={{ maxCalls, exemptCalls }}
            onCallLimitsChange={({ maxCalls: nextMax, exemptCalls: nextExempt }) => {
              setMaxCalls(nextMax)
              setExemptCalls(nextExempt)
            }}
            advancedVariant="accordion"
            advancedOpen={accordionValue === 'advanced'}
            onAdvancedOpenChange={openValue => setAccordionValue(openValue ? 'advanced' : '')}
            advancedDescription={t('knowledge:document.advancedSettings.collapsed')}
            showRetrievalSection={true}
            retrievalConfig={retrievalConfig}
            onRetrievalConfigChange={setRetrievalConfig}
            retrievalScope={scope}
            retrievalGroupName={groupName}
          />

          {/* Group Selector - only show when enabled */}
          {showGroupSelector && (
            <div className="space-y-2">
              <Label>{t('knowledge:document.knowledgeBase.linkedGroup')}</Label>
              <Select
                value={selectedGroup || 'none'}
                onValueChange={value => handleGroupChange(value === 'none' ? null : value)}
                disabled={loadingGroups}
              >
                <SelectTrigger className="w-full">
                  <SelectValue
                    placeholder={t('knowledge:document.knowledgeBase.selectGroupPlaceholder')}
                  />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">
                    <div className="flex items-center gap-2">
                      <span>{t('knowledge:document.knowledgeBase.noGroup')}</span>
                    </div>
                  </SelectItem>
                  {manageableGroups.map(group => (
                    <SelectItem key={group.name} value={group.name}>
                      <div className="flex items-center gap-2">
                        <Users className="w-4 h-4 text-text-muted" />
                        <span>{group.display_name || group.name}</span>
                      </div>
                    </SelectItem>
                  ))}
                  {/* Show preSelectedGroup if it's not in manageableGroups */}
                  {preSelectedGroup && !manageableGroups.find(g => g.name === preSelectedGroup) && (
                    <SelectItem key={preSelectedGroup} value={preSelectedGroup}>
                      <div className="flex items-center gap-2">
                        <Users className="w-4 h-4 text-text-muted" />
                        <span>{preSelectedGroup}</span>
                      </div>
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
              <p className="text-xs text-text-muted">
                {t('knowledge:document.knowledgeBase.linkedGroupHint')}
              </p>
            </div>
          )}

          {error && <p className="text-sm text-error">{error}</p>}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={loading}
            className="h-11 min-w-[44px]"
          >
            {t('common:actions.cancel')}
          </Button>
          <Button
            onClick={handleSubmit}
            variant="primary"
            disabled={loading}
            className="h-11 min-w-[44px]"
          >
            {loading ? t('common:actions.creating') : t('common:actions.create')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
