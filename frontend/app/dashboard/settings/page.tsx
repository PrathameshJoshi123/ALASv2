"use client";

import { useState } from "react";
import { User, Bell, Shield, Save } from "lucide-react";
import toast from "react-hot-toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function SettingsPage() {
  const [loading, setLoading] = useState(false);
  const [profileData, setProfileData] = useState({
    name: "Senior Associate",
    email: "associate@lexington.com",
    firm: "Lexington & Co",
    jurisdiction: "India (Pan-State / Supreme Court & Delhi High Court)",
  });

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      toast.success("Preferences saved successfully");
    }, 600);
  };

  return (
    <div className="p-8 lg:p-10 max-w-4xl mx-auto space-y-8">
      {/* 1. Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
            <span>System</span> / <span>Settings & Configuration</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Workspace Preferences
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your firm profile, statutory presets, and Indian Kanoon research defaults.
          </p>
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Firm & Advocate Profile</CardTitle>
            <CardDescription className="text-xs">
              Entity identification used on exportable legal dossiers and contract headers
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">
                  Practitioner Name
                </label>
                <Input
                  type="text"
                  value={profileData.name}
                  onChange={(e) =>
                    setProfileData({ ...profileData, name: e.target.value })
                  }
                  className="text-xs h-9"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">
                  Official Email Address
                </label>
                <Input
                  type="email"
                  value={profileData.email}
                  onChange={(e) =>
                    setProfileData({ ...profileData, email: e.target.value })
                  }
                  className="text-xs h-9"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">
                  Firm / Legal Department
                </label>
                <Input
                  type="text"
                  value={profileData.firm}
                  onChange={(e) =>
                    setProfileData({ ...profileData, firm: e.target.value })
                  }
                  className="text-xs h-9"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">
                  Default Legal Jurisdiction
                </label>
                <Input
                  type="text"
                  value={profileData.jurisdiction}
                  onChange={(e) =>
                    setProfileData({ ...profileData, jurisdiction: e.target.value })
                  }
                  className="text-xs h-9"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Statutory & AI Configuration</CardTitle>
            <CardDescription className="text-xs">
              Autonomous analysis rules applied during contract and case ingestion
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between p-3 rounded-md border border-border bg-muted/20">
              <div>
                <p className="text-xs font-semibold text-foreground">
                  Indian Kanoon Live Precedent Retrieval
                </p>
                <p className="text-[11px] text-muted-foreground">
                  Automatically query High Court and Supreme Court case precedents for flagged clauses.
                </p>
              </div>
              <Badge variant="success">Enabled</Badge>
            </div>

            <div className="flex items-center justify-between p-3 rounded-md border border-border bg-muted/20">
              <div>
                <p className="text-xs font-semibold text-foreground">
                  Strict ICA Section 27 Restraint Check
                </p>
                <p className="text-[11px] text-muted-foreground">
                  Flag all non-compete clauses as void per Percept D'Mark and Niranjan Shankar Golikari standards.
                </p>
              </div>
              <Badge variant="success">Strict</Badge>
            </div>
          </CardContent>
        </Card>

        <div className="flex items-center justify-end">
          <Button type="submit" loading={loading} className="text-xs">
            <Save className="w-3.5 h-3.5 mr-1.5" />
            Save Preferences
          </Button>
        </div>
      </form>
    </div>
  );
}
