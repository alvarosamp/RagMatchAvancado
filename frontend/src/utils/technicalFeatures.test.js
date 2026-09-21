import { describe, expect, it } from 'vitest'

import { flattenTechnicalFeatures, summarizeTechnicalFeatures } from './technicalFeatures'

describe('technicalFeatures V8', () => {
  const features = {
    transceiver: {
      identificacao: { form_factor: 'SFP+', velocidade_nominal_gbps: '10' },
      fibra_conector: { tipo_fibra: 'Monomodo', alcance_m: 'N/C' },
    },
  }

  it('flatten nested V8 blocks and omits N/C', () => {
    expect(flattenTechnicalFeatures(features)).toEqual([
      { path: 'transceiver.identificacao.form_factor', label: 'form factor', value: 'SFP+' },
      { path: 'transceiver.identificacao.velocidade_nominal_gbps', label: 'velocidade nominal gbps', value: '10' },
      { path: 'transceiver.fibra_conector.tipo_fibra', label: 'tipo fibra', value: 'Monomodo' },
    ])
  })

  it('builds a readable summary instead of object stringification', () => {
    expect(summarizeTechnicalFeatures(features)).toBe('SFP+ / 10 / Monomodo')
  })
})
