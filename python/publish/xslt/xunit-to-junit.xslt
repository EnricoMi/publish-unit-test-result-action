<?xml version="1.0" encoding="UTF-8" ?>
<!-- based on https://gist.github.com/cdroulers/e23eeb31d6c1c2cade6f680e321aed8d -->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="xml" indent="yes"/>
  <xsl:template match="/">
    <testsuites>
      <xsl:for-each select="//assembly">
        <testsuite>
          <xsl:attribute name="name"><xsl:value-of select="@name"/></xsl:attribute>
          <xsl:attribute name="tests"><xsl:value-of select="@total"/></xsl:attribute>
          <xsl:attribute name="failures"><xsl:value-of select="@failed"/></xsl:attribute>
          <xsl:if test="@errors">
            <xsl:attribute name="errors"><xsl:value-of select="@errors"/></xsl:attribute>
          </xsl:if>
          <xsl:attribute name="time"><xsl:value-of select="@time"/></xsl:attribute>
          <xsl:attribute name="skipped"><xsl:value-of select="@skipped"/></xsl:attribute>
          <xsl:attribute name="timestamp"><xsl:value-of select="@run-date"/>T<xsl:value-of select="@run-time"/></xsl:attribute>

          <xsl:for-each select="collection | class">
            <testsuite>
              <xsl:attribute name="name"><xsl:value-of select="@name"/></xsl:attribute>
              <xsl:attribute name="tests"><xsl:value-of select="@total"/></xsl:attribute>
              <xsl:attribute name="failures"><xsl:value-of select="@failed"/></xsl:attribute>
              <xsl:if test="@errors">
                <xsl:attribute name="errors"><xsl:value-of select="@errors"/></xsl:attribute>
              </xsl:if>
              <xsl:attribute name="time"><xsl:value-of select="@time"/></xsl:attribute>
              <xsl:attribute name="skipped"><xsl:value-of select="@skipped"/></xsl:attribute>

              <xsl:for-each select="test">
                <testcase>
                  <xsl:attribute name="name"><xsl:value-of select="@method"/></xsl:attribute>
                  <xsl:attribute name="time"><xsl:value-of select="@time"/></xsl:attribute>
                  <xsl:attribute name="classname"><xsl:value-of select="@type"/></xsl:attribute>
                  <xsl:if test="reason">
                    <skipped>
                      <xsl:attribute name="message"><xsl:value-of select="reason/text()"/></xsl:attribute>
                    </skipped>
                  </xsl:if>
                  <xsl:apply-templates select="failure"/>
                </testcase>
              </xsl:for-each>

              </testsuite>
          </xsl:for-each>

        </testsuite>
      </xsl:for-each>
    </testsuites>
  </xsl:template>

  <xsl:template match="failure">
    <failure>
      <xsl:if test="@exception-type">
        <xsl:attribute name="type"><xsl:value-of select="@exception-type"/></xsl:attribute>
      </xsl:if>
      <xsl:attribute name="message"><xsl:value-of select="message"/></xsl:attribute>
      <xsl:value-of select="message"/>
      <xsl:value-of select="stack-trace"/>
     </failure>
  </xsl:template>

</xsl:stylesheet>
