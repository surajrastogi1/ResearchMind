const AuthShell = ({ eyebrow, title, description, children, footer }) => {
  return (
    <main className="auth-page">
      <section className="auth-intro">
        <div className="size-14"><img src="/logo (2).png" alt="" /></div>
        <div className="intro-copy">
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p className="intro-description">{description}</p>
        </div>
        <p className="intro-note">Read deeply.<br />Remember clearly.</p>
      </section>
      <section className="auth-panel" aria-label="Account form">
        <div className="auth-panel-inner">
          {children}
          <p className="auth-footer">{footer}</p>
        </div>
      </section>
    </main>
  )
}

export default AuthShell