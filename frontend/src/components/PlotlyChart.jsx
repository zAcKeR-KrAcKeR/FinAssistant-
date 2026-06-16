import Plot from 'react-plotly.js'

export default function PlotlyChart({ spec, style = {} }) {
  if (!spec) return null
  return (
    <Plot
      data={spec.data || []}
      layout={{
        autosize: true,
        ...(spec.layout || {}),
      }}
      config={{
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        responsive: true,
      }}
      style={{ width: '100%', minHeight: 320, ...style }}
      useResizeHandler
    />
  )
}
