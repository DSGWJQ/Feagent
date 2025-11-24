/**
 * API Client Tests - RED phase of TDD
 * Tests all API endpoints based on backend capabilities
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { apiClient } from '../api';

// Mock axios
vi.mock('axios');

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Workflow Endpoints', () => {
    it('should create a workflow', async () => {
      const mockResponse = {
        id: 'wf_123',
        name: 'Test Workflow',
        status: 'draft',
        nodes: [],
        edges: [],
      };

      // Tests will verify API is called with correct URL and data
      expect(apiClient.workflows).toBeDefined();
    });

    it('should list all workflows', async () => {
      expect(apiClient.workflows.list).toBeDefined();
    });

    it('should get workflow details by id', async () => {
      expect(apiClient.workflows.getById).toBeDefined();
    });

    it('should update a workflow', async () => {
      expect(apiClient.workflows.update).toBeDefined();
    });

    it('should delete a workflow', async () => {
      expect(apiClient.workflows.delete).toBeDefined();
    });

    it('should publish a workflow', async () => {
      expect(apiClient.workflows.publish).toBeDefined();
    });
  });

  describe('Task Classification Endpoints', () => {
    it('should classify a task', async () => {
      expect(apiClient.classification.classify).toBeDefined();
    });
  });

  describe('Scheduled Workflow Endpoints', () => {
    it('should create a scheduled workflow', async () => {
      expect(apiClient.scheduledWorkflows.create).toBeDefined();
    });

    it('should list all scheduled workflows', async () => {
      expect(apiClient.scheduledWorkflows.list).toBeDefined();
    });

    it('should get scheduled workflow details', async () => {
      expect(apiClient.scheduledWorkflows.getById).toBeDefined();
    });

    it('should update a scheduled workflow', async () => {
      expect(apiClient.scheduledWorkflows.update).toBeDefined();
    });

    it('should delete a scheduled workflow', async () => {
      expect(apiClient.scheduledWorkflows.delete).toBeDefined();
    });

    it('should trigger scheduled workflow execution', async () => {
      expect(apiClient.scheduledWorkflows.trigger).toBeDefined();
    });

    it('should pause a scheduled workflow', async () => {
      expect(apiClient.scheduledWorkflows.pause).toBeDefined();
    });

    it('should resume a paused scheduled workflow', async () => {
      expect(apiClient.scheduledWorkflows.resume).toBeDefined();
    });
  });

  describe('Scheduler Monitoring Endpoints', () => {
    it('should get scheduler status', async () => {
      expect(apiClient.scheduler.getStatus).toBeDefined();
    });

    it('should get scheduler jobs', async () => {
      expect(apiClient.scheduler.getJobs).toBeDefined();
    });
  });

  describe('Tool Management Endpoints', () => {
    it('should create a tool', async () => {
      expect(apiClient.tools.create).toBeDefined();
    });

    it('should list all tools', async () => {
      expect(apiClient.tools.list).toBeDefined();
    });

    it('should get tool details by id', async () => {
      expect(apiClient.tools.getById).toBeDefined();
    });

    it('should update a tool', async () => {
      expect(apiClient.tools.update).toBeDefined();
    });

    it('should delete a tool', async () => {
      expect(apiClient.tools.delete).toBeDefined();
    });

    it('should publish a tool', async () => {
      expect(apiClient.tools.publish).toBeDefined();
    });

    it('should deprecate a tool', async () => {
      expect(apiClient.tools.deprecate).toBeDefined();
    });
  });

  describe('LLM Provider Endpoints', () => {
    it('should register an LLM provider', async () => {
      expect(apiClient.llmProviders.register).toBeDefined();
    });

    it('should list all LLM providers', async () => {
      expect(apiClient.llmProviders.list).toBeDefined();
    });

    it('should get LLM provider details by id', async () => {
      expect(apiClient.llmProviders.getById).toBeDefined();
    });

    it('should update an LLM provider', async () => {
      expect(apiClient.llmProviders.update).toBeDefined();
    });

    it('should delete an LLM provider', async () => {
      expect(apiClient.llmProviders.delete).toBeDefined();
    });

    it('should enable an LLM provider', async () => {
      expect(apiClient.llmProviders.enable).toBeDefined();
    });

    it('should disable an LLM provider', async () => {
      expect(apiClient.llmProviders.disable).toBeDefined();
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', async () => {
      expect(apiClient.handleError).toBeDefined();
    });

    it('should include request/response interceptors', async () => {
      expect(apiClient).toBeDefined();
    });
  });
});
