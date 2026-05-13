// SPDX-FileCopyrightText: 2025 Weibo, Inc.
//
// SPDX-License-Identifier: Apache-2.0

/**
 * DingTalk document API functions.
 */

import client from './client'
import type {
  DingtalkDocTreeResponse,
  DingtalkSyncStatus,
  DingtalkSyncResult,
} from '@/types/dingtalk-doc'

export const dingtalkDocApi = {
  /**
   * Get all synced DingTalk document nodes as a tree structure.
   */
  getDocs: async (): Promise<DingtalkDocTreeResponse> => {
    return client.get<DingtalkDocTreeResponse>('/dingtalk-docs')
  },

  /**
   * Trigger sync of DingTalk documents from the user's MCP server.
   */
  syncDocs: async (): Promise<DingtalkSyncResult> => {
    return client.post<DingtalkSyncResult>('/dingtalk-docs/sync')
  },

  /**
   * Get the sync status for the current user.
   */
  getSyncStatus: async (): Promise<DingtalkSyncStatus> => {
    return client.get<DingtalkSyncStatus>('/dingtalk-docs/sync-status')
  },

  /**
   * Delete a synced document node from local cache.
   */
  deleteDoc: async (nodeId: number): Promise<void> => {
    await client.delete(`/dingtalk-docs/${nodeId}`)
  },

  /**
   * Get all synced DingTalk personal wikispace (我的知识库) nodes as a tree structure.
   */
  getMyWikispaceNodes: async (): Promise<DingtalkDocTreeResponse> => {
    return client.get<DingtalkDocTreeResponse>('/dingtalk-my-wikispace')
  },

  /**
   * Trigger sync of DingTalk personal wikispace (我的知识库) nodes from the user's wikispace MCP server.
   */
  syncMyWikispaceNodes: async (): Promise<DingtalkSyncResult> => {
    return client.post<DingtalkSyncResult>('/dingtalk-my-wikispace/sync')
  },

  /**
   * Get the personal wikispace (我的知识库) sync status for the current user.
   */
  getMyWikispaceSyncStatus: async (): Promise<DingtalkSyncStatus> => {
    return client.get<DingtalkSyncStatus>('/dingtalk-my-wikispace/sync-status')
  },

  /**
   * Get all synced DingTalk organization wikispace (组织知识库) nodes as a tree structure.
   */
  getOrgWikispaceNodes: async (): Promise<DingtalkDocTreeResponse> => {
    return client.get<DingtalkDocTreeResponse>('/dingtalk-org-wikispace')
  },

  /**
   * Trigger sync of DingTalk organization wikispace (组织知识库) nodes from the user's wikispace MCP server.
   */
  syncOrgWikispaceNodes: async (): Promise<DingtalkSyncResult> => {
    return client.post<DingtalkSyncResult>('/dingtalk-org-wikispace/sync')
  },

  /**
   * Get the organization wikispace (组织知识库) sync status for the current user.
   */
  getOrgWikispaceSyncStatus: async (): Promise<DingtalkSyncStatus> => {
    return client.get<DingtalkSyncStatus>('/dingtalk-org-wikispace/sync-status')
  },
}
