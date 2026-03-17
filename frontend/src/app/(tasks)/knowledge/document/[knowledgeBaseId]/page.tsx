// SPDX-FileCopyrightText: 2025 Weibo, Inc.
//
// SPDX-License-Identifier: Apache-2.0

'use client'

import { Suspense } from 'react'
import dynamic from 'next/dynamic'
import { useParams, useRouter } from 'next/navigation'
import '@/app/tasks/tasks.css'
import '@/features/common/scrollbar.css'
import { useIsMobile } from '@/features/layout/hooks/useMediaQuery'
import { TaskParamSync } from '@/features/tasks/components/params'
import { Spinner } from '@/components/ui/spinner'
import { useKnowledgeBaseDetail } from '@/features/knowledge/document/hooks'
import { useTranslation } from '@/hooks/useTranslation'
import { ShieldAlert, ArrowLeft } from 'lucide-react'

// Loading fallback component for dynamic imports
function PageLoadingFallback() {
  return (
    <div className="flex h-screen items-center justify-center bg-base">
      <Spinner />
    </div>
  )
}

// Access denied error component
function AccessDeniedError({ onBack }: { onBack: () => void }) {
  const { t } = useTranslation('knowledge')
  return (
    <div className="flex h-screen items-center justify-center bg-base">
      <div className="flex flex-col items-center max-w-md px-6 text-center">
        <ShieldAlert className="w-16 h-16 text-text-muted mb-4" />
        <h2 className="text-xl font-semibold text-text-primary mb-2">
          {t('document.accessDenied.title')}
        </h2>
        <p className="text-sm text-text-secondary mb-6">{t('document.accessDenied.description')}</p>
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10 rounded-md transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          {t('document.accessDenied.backButton')}
        </button>
      </div>
    </div>
  )
}

// Dynamic imports for notebook type (three-column layout with chat)
const KnowledgeBaseChatPageDesktop = dynamic(
  () =>
    import('./KnowledgeBaseChatPageDesktop').then(mod => ({
      default: mod.KnowledgeBaseChatPageDesktop,
    })),
  {
    ssr: false,
    loading: PageLoadingFallback,
  }
)

const KnowledgeBaseChatPageMobile = dynamic(
  () =>
    import('./KnowledgeBaseChatPageMobile').then(mod => ({
      default: mod.KnowledgeBaseChatPageMobile,
    })),
  {
    ssr: false,
    loading: PageLoadingFallback,
  }
)

// Dynamic imports for classic type (document list only)
const KnowledgeBaseClassicPageDesktop = dynamic(
  () =>
    import('./KnowledgeBaseClassicPageDesktop').then(mod => ({
      default: mod.KnowledgeBaseClassicPageDesktop,
    })),
  {
    ssr: false,
    loading: PageLoadingFallback,
  }
)

const KnowledgeBaseClassicPageMobile = dynamic(
  () =>
    import('./KnowledgeBaseClassicPageMobile').then(mod => ({
      default: mod.KnowledgeBaseClassicPageMobile,
    })),
  {
    ssr: false,
    loading: PageLoadingFallback,
  }
)

/**
 * Knowledge Base Page Router Component
 *
 * Routes between different layouts based on:
 * 1. Knowledge base type (kb_type):
 *    - 'notebook': Three-column layout with chat area and document panel
 *    - 'classic': Document list only without chat functionality
 * 2. Screen size:
 *    - Mobile: ≤767px - Touch-optimized UI with drawer sidebar
 *    - Desktop: ≥768px - Full-featured UI with resizable sidebar
 *
 * Uses dynamic imports to optimize bundle size and loading performance.
 */
export default function KnowledgeBaseChatPage() {
  // Mobile detection
  const isMobile = useIsMobile()
  const params = useParams()
  const router = useRouter()

  // Parse knowledge base ID from URL
  const knowledgeBaseId = params.knowledgeBaseId
    ? parseInt(params.knowledgeBaseId as string, 10)
    : null

  // Fetch knowledge base details to determine type
  // This hook is the single source of truth for kb_type routing
  const {
    knowledgeBase,
    loading,
    error,
    refresh: refreshKnowledgeBase,
  } = useKnowledgeBaseDetail({
    knowledgeBaseId: knowledgeBaseId || 0,
    autoLoad: !!knowledgeBaseId,
  })

  // Handle back navigation
  const handleBack = () => {
    router.push('/tasks?type=document')
  }

  // Show loading while fetching knowledge base info
  if (loading) {
    return <PageLoadingFallback />
  }

  // Show access denied error when fetch fails (403/404)
  if (error || !knowledgeBase) {
    return <AccessDeniedError onBack={handleBack} />
  }

  // Determine the layout type (default to 'notebook' if not specified)
  const kbType = knowledgeBase.kb_type || 'notebook'

  // Route to appropriate component based on type and screen size
  if (kbType === 'classic') {
    return (
      <>
        {/* TaskParamSync handles URL taskId parameter synchronization with TaskContext */}
        <Suspense>
          <TaskParamSync />
        </Suspense>
        {isMobile ? (
          <KnowledgeBaseClassicPageMobile onKbTypeChanged={refreshKnowledgeBase} />
        ) : (
          <KnowledgeBaseClassicPageDesktop onKbTypeChanged={refreshKnowledgeBase} />
        )}
      </>
    )
  }

  // Default: notebook type (three-column layout with chat)
  return (
    <>
      {/* TaskParamSync handles URL taskId parameter synchronization with TaskContext */}
      <Suspense>
        <TaskParamSync />
      </Suspense>
      {isMobile ? (
        <KnowledgeBaseChatPageMobile onKbTypeChanged={refreshKnowledgeBase} />
      ) : (
        <KnowledgeBaseChatPageDesktop onKbTypeChanged={refreshKnowledgeBase} />
      )}
    </>
  )
}
