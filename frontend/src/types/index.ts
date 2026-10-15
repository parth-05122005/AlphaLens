export interface User {
  id: number
  username: string
  email: string
}

export interface AuthResponse {
  user: User
  access: string
  refresh: string
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface TaskAccepted {
  task_id: string
}

export type TaskState = 'PENDING' | 'STARTED' | 'RETRY' | 'SUCCESS' | 'FAILURE' | 'REVOKED'

export interface TaskStatus {
  task_id: string
  state: TaskState
  ready: boolean
}
