import { useRef, useState, type DragEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { errorMessage } from '../api/client'
import { uploadDocument } from '../api/research'
import { useToast } from './Toast'
import { Spinner } from './ui'

const MAX_BYTES = 10 * 1024 * 1024

export default function PdfUpload({ holdingId }: { holdingId?: number }) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const upload = useMutation({
    mutationFn: (file: File) => uploadDocument(file, holdingId),
    onSuccess: (doc) => {
      toast(`Uploaded “${doc.title}”. Indexing in the background…`, 'info')
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (err) => toast(errorMessage(err, 'Upload failed'), 'error'),
  })

  function handle(files: FileList | null) {
    const file = files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) return toast('Only PDF files are supported', 'error')
    if (file.size > MAX_BYTES) return toast('PDF must be 10 MB or smaller', 'error')
    upload.mutate(file)
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    handle(e.dataTransfer.files)
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => input.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
      className={`flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed px-4 py-6 text-center text-sm transition ${
        dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 hover:border-slate-400 hover:bg-slate-50'
      }`}
    >
      <input ref={input} type="file" accept="application/pdf,.pdf" className="hidden" onChange={(e) => handle(e.target.files)} />
      {upload.isPending ? (
        <span className="flex items-center gap-2 text-slate-600">
          <Spinner /> Extracting text…
        </span>
      ) : (
        <>
          <span className="font-medium text-slate-700">Drop a PDF here or click to choose</span>
          <span className="text-xs text-slate-500">Annual reports, earnings call transcripts, broker notes · max 10 MB</span>
        </>
      )}
    </div>
  )
}
