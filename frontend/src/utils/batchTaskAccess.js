export function createBatchTaskContext(response) {
  if (!response?.task_id) return null
  return {
    taskId: response.task_id,
    accessToken: response.access_token || null,
  }
}

export function batchTaskHeaders(taskContext) {
  if (!taskContext?.accessToken) return {}
  return {
    'X-Task-Access-Token': taskContext.accessToken,
  }
}

