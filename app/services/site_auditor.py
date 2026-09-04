class SiteAuditor:
    async def full_audit(self, domain: str):
        return type('obj', (object,), {
            'domain': domain,
            'overall_score': 75,
            'categories': {'technical': 80, 'security': 70, 'seo': 75, 'performance': 75},
            'issues': [],
            'metadata': {},
            'timestamp': '2026-01-01',
            'model_dump': lambda self, **kwargs: {
                'domain': self.domain,
                'overall_score': self.overall_score,
                'categories': self.categories,
                'issues': self.issues,
                'metadata': self.metadata,
                'timestamp': self.timestamp
            }
        })()
