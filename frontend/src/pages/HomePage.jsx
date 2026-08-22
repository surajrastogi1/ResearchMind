import { useEffect, useRef, useState } from 'react'
import { API_URL } from '../api.js'

const HomePage = ({ onNavigate }) => {
  const [projects, setProjects] = useState([])
  const [selectedProject, setSelectedProject] = useState(null)
  const [documents, setDocuments] = useState({})
  const [isCreating, setIsCreating] = useState(false)
  const [projectForm, setProjectForm] = useState({ name: '', description: '' })
  const [notice, setNotice] = useState('')
  const [activeTool, setActiveTool] = useState(null)
  const [selectedDocument, setSelectedDocument] = useState(null)
  const [toolResult, setToolResult] = useState(null)
  const [toolLoading, setToolLoading] = useState(false)
  const [question, setQuestion] = useState('')
  const uploadRefs = useRef({})
  const username = localStorage.getItem('username') || 'researcher'

  const request = async (path, options = {}) => {
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}`, ...options.headers },
    })
    if (response.status === 401) throw new Error('Your session has expired.')
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || 'Something went wrong.')
    return data
  }

  useEffect(() => {
    request('/projects').then((data) => {
      setProjects(data)
      setSelectedProject(data[0] || null)
    }).catch((error) => setNotice(error.message))
  }, [])

  const createProject = async (event) => {
    event.preventDefault()
    if (!projectForm.name.trim()) return
    try {
      const data = await request('/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(projectForm),
      })
      const project = data.project
      setProjects((current) => [...current, project])
      setSelectedProject(project)
      setProjectForm({ name: '', description: '' })
      setIsCreating(false)
      setNotice('Project created.')
    } catch (error) {
      setNotice(error.message)
    }
  }

  const uploadPdf = async (project, event) => {
    const file = event.target.files[0]
    if (!file) return
    try {
      const body = new FormData()
      body.append('file', file)
      const upload = await request(`/projects/${project.id}/upload`, { method: 'POST', body })
      const document = { id: upload.db_record_id, name: file.name, status: 'processing' }
      setDocuments((current) => ({ ...current, [project.id]: [...(current[project.id] || []), document] }))
      setSelectedProject(project)
      setNotice(`${file.name} uploaded. Preparing its research context...`)
      request(`/projects/${project.id}/pdfs/${upload.db_record_id}/read`, { method: 'GET' }).then(() => {
        setDocuments((current) => ({ ...current, [project.id]: (current[project.id] || []).map((item) => item.id === document.id ? { ...item, status: 'ready' } : item) }))
        setNotice(`${file.name} is ready to study.`)
      }).catch((error) => {
        setDocuments((current) => ({ ...current, [project.id]: (current[project.id] || []).map((item) => item.id === document.id ? { ...item, status: 'error' } : item) }))
        setNotice(`Could not process ${file.name}: ${error.message}`)
      })
    } catch (error) {
      setNotice(error.message)
    }
    event.target.value = ''
  }

  const deleteDocument = (projectId, documentId) => {
    setDocuments((current) => ({ ...current, [projectId]: (current[projectId] || []).filter((document) => document.id !== documentId) }))
    if (selectedDocument?.id === documentId) {
      setSelectedDocument(null)
      setActiveTool(null)
    }
    setNotice('Document removed from this dashboard view.')
  }

  const openTool = (tool, document) => {
    if (document.status !== 'ready') return
    setSelectedDocument(document)
    setActiveTool(tool)
    setToolResult(null)
    setQuestion('')
  }

  const runTool = async () => {
    if (!selectedProject || !selectedDocument || !activeTool) return
    setToolLoading(true)
    setToolResult(null)
    try {
      const query = activeTool === 'chat' ? `?question=${encodeURIComponent(question)}` : ''
      const method = activeTool === 'chat' ? 'POST' : 'POST'
      const data = await request(`/projects/${selectedProject.id}/pdfs/${selectedDocument.id}/${activeTool}${query}`, { method })
      setToolResult(data)
    } catch (error) {
      setToolResult({ error: error.message })
    } finally {
      setToolLoading(false)
    }
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('username')
    onNavigate('/login')
  }

  const selectedDocuments = selectedProject ? documents[selectedProject.id] || [] : []

  return (
    <main className="dashboard-page">
      <header className="dashboard-header">
        <a className="dashboard-brand" href="/home" onClick={(event) => { event.preventDefault(); onNavigate('/home') }}>
          <img src="/logo (2).png" alt="" />
          <span>ResearchMind</span>
        </a>
        <div className="dashboard-user">
          <span className="user-greeting">Good to see you, <strong>{username}</strong></span>
          <button className="logout-button" type="button" onClick={logout}>Log out</button>
        </div>
      </header>

      <div className="dashboard-body">
        <aside className="project-sidebar">
          <div className="sidebar-heading"><span>Your projects</span><span className="project-count">{projects.length}</span></div>
          <button className="new-project-button" type="button" onClick={() => setIsCreating(true)}><span>+</span> New project</button>
          <div className="project-list">
            {projects.map((project) => (
              <button className={`project-item ${selectedProject?.id === project.id ? 'active' : ''}`} key={project.id} type="button" onClick={() => setSelectedProject(project)}>
                <span className="project-icon">{project.name.slice(0, 1).toUpperCase()}</span>
                <span><strong>{project.name}</strong><small>{(documents[project.id] || []).length} documents</small></span>
              </button>
            ))}
            {!projects.length && <p className="empty-sidebar">Your first project starts here.</p>}
          </div>
        </aside>

        <section className="workspace-content">
          <div className="workspace-heading">
            <div><p className="eyebrow">Your research desk</p><h1>Make sense of<br /><em>what you read.</em></h1></div>
            <p className="workspace-intro">Bring your source material together, then let your thinking take the lead.</p>
          </div>

          {notice && <p className="dashboard-notice" role="status">{notice}</p>}

          {!selectedProject ? (
            <div className="empty-workspace"><span className="empty-number">01</span><h2>Create a project to begin.</h2><p>Give a research question its own home for PDFs, notes, and conversation.</p><button className="primary-dashboard-button" type="button" onClick={() => setIsCreating(true)}>Create your first project</button></div>
          ) : (
            <>
              <div className="active-project-bar"><div><span className="section-label">Current project</span><h2>{selectedProject.name}</h2><p>{selectedProject.description || 'A focused space for your source material.'}</p></div><label className="upload-button">+ Add PDF<input ref={(element) => { uploadRefs.current[selectedProject.id] = element }} type="file" accept="application/pdf" onChange={(event) => uploadPdf(selectedProject, event)} /></label></div>
              <div className="document-stage">
                <div className="stage-heading"><div><span className="section-label">Study tools</span><h2>Choose your way in.</h2></div><span className="document-total">{selectedDocuments.length} PDF{selectedDocuments.length === 1 ? '' : 's'} in project</span></div>
                {selectedDocuments.length ? <div className="document-strip">{selectedDocuments.map((document) => <div className={`document-chip ${document.status}`} key={document.id}><button type="button" className="document-select" onClick={() => setSelectedDocument(document)}><span>PDF</span>{document.name}</button><small>{document.status === 'processing' ? 'Embedding...' : document.status === 'error' ? 'Failed' : 'Ready'}</small><button type="button" className="document-delete" aria-label={`Remove ${document.name}`} onClick={() => deleteDocument(selectedProject.id, document.id)}>×</button></div>)}</div> : <div className="drop-zone" onClick={() => uploadRefs.current[selectedProject.id]?.click()}><span className="drop-symbol">+</span><div><strong>Drop a PDF here, or browse</strong><p>Upload as many source documents as your project needs.</p></div></div>}
                <div className="tool-grid">{[['01', 'Chat with your PDFs', 'Ask questions and follow the thread of an idea.', 'chat'], ['02', 'Build a clear summary', 'Turn long papers into the shape of the argument.', 'summary'], ['03', 'Study actively', 'Generate notes, flashcards, and quizzes from context.', 'notes']].map(([number, title, description, tool]) => <article className="tool-card" key={number}><span>{number}</span><h3>{title}</h3><p>{description}</p><button type="button" disabled={!selectedDocuments.some((document) => document.status === 'ready')} onClick={() => openTool(tool, selectedDocuments.find((document) => document.status === 'ready'))}>Open tool <span>↗</span></button></article>)}</div>
              </div>
            </>
          )}
        </section>
      </div>

      {isCreating && <div className="modal-backdrop" role="presentation" onClick={(event) => event.target === event.currentTarget && setIsCreating(false)}><form className="project-modal" onSubmit={createProject}><button className="modal-close" type="button" aria-label="Close" onClick={() => setIsCreating(false)}>×</button><p className="eyebrow">New workspace</p><h2>Name your next question.</h2><p>Projects keep your PDFs and generated study material together.</p><div className="field-group"><label htmlFor="project-name">Project name</label><input id="project-name" value={projectForm.name} onChange={(event) => setProjectForm({ ...projectForm, name: event.target.value })} placeholder="e.g. Cognitive science review" autoFocus required /></div><div className="field-group"><label htmlFor="project-description">Description <span>(optional)</span></label><textarea id="project-description" value={projectForm.description} onChange={(event) => setProjectForm({ ...projectForm, description: event.target.value })} placeholder="What are you trying to understand?" rows="3" /></div><button className="submit-button" type="submit">Create project</button></form></div>}
      {activeTool && <div className="modal-backdrop tool-backdrop" role="presentation" onClick={(event) => event.target === event.currentTarget && setActiveTool(null)}><section className="tool-modal" aria-label="PDF study tool"><button className="modal-close" type="button" aria-label="Close" onClick={() => setActiveTool(null)}>×</button><p className="eyebrow">{selectedDocument?.name}</p><h2>{activeTool === 'chat' ? 'Ask the paper.' : activeTool === 'summary' ? 'The argument, distilled.' : 'Study from the source.'}</h2>{activeTool === 'chat' ? <div className="chat-panel"><div className="chat-answer">{toolResult?.answer || 'Ask a question about this document and the relevant context will appear here.'}</div><div className="chat-input"><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What is the main argument?" onKeyDown={(event) => event.key === 'Enter' && question.trim() && runTool()} /><button type="button" onClick={runTool} disabled={!question.trim() || toolLoading}>{toolLoading ? '...' : 'Ask'}</button></div></div> : <><p className="tool-modal-copy">Generate material grounded in the embedded text of this PDF.</p><div className="tool-choice-grid"><button type="button" onClick={() => setActiveTool('summary')}>Summary</button><button type="button" onClick={() => setActiveTool('notes')}>Notes</button><button type="button" onClick={() => setActiveTool('flashcards')}>Flashcards</button><button type="button" onClick={() => setActiveTool('quiz')}>Quiz</button></div><button className="submit-button" type="button" onClick={runTool} disabled={toolLoading}>{toolLoading ? 'Generating...' : `Generate ${activeTool}`}</button>{toolResult && <div className="generated-result">{toolResult.error || toolResult.summary || toolResult.study_notes || (toolResult.flashcards && `${toolResult.count} flashcards generated.`) || (toolResult.quiz && `${toolResult.total_questions} quiz questions generated.`)}</div>}</>}</section></div>}
    </main>
  )
}

export default HomePage
