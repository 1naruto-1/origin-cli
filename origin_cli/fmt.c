#include <Origin.h>

// 取对象：nPlot>=0 为数据图；strObj 非空为图形对象；否则为图层（nLayer<0 为页面）
// 读格式树并存为 XML
int fmt_dump(string strGraph, int nLayer, int nPlot, string strObj, string strFile)
{
	GraphPage gp(strGraph);
	if(!gp)
		return -1;
	Tree tr;
	if(nLayer < 0)
		tr = gp.GetFormat(FPB_ALL, FOB_ALL, TRUE, TRUE);
	else
	{
		GraphLayer gl = gp.Layers(nLayer);
		if(!gl)
			return -1;
		if(nPlot >= 0)
		{
			DataPlot dp = gl.DataPlots(nPlot);
			if(!dp)
				return -1;
			tr = dp.GetFormat(FPB_ALL, FOB_ALL, TRUE, TRUE);
		}
		else if(strObj.GetLength() > 0)
		{
			GraphObject go = gl.GraphObjects(strObj);
			if(!go)
				return -1;
			tr = go.GetFormat(FPB_ALL, FOB_ALL, TRUE, TRUE);
		}
		else
			tr = gl.GetFormat(FPB_ALL, FOB_ALL, TRUE, TRUE);
	}
	return tr.Save(strFile) ? 0 : -2;
}

// 应用只含目标节点的小格式树（XML 文件，节点按名字匹配，NodeID 由 UpdateThemeIDs 补上）
int fmt_apply(string strGraph, int nLayer, int nPlot, string strObj, string strFile)
{
	GraphPage gp(strGraph);
	if(!gp)
		return -1;
	Tree tr;
	if(!tr.Load(strFile))
		return -2;
	int nBad;
	bool bOK;
	if(nLayer < 0)
	{
		nBad = gp.UpdateThemeIDs(tr.Root);
		bOK = gp.ApplyFormat(tr, TRUE, TRUE);
	}
	else
	{
		GraphLayer gl = gp.Layers(nLayer);
		if(!gl)
			return -1;
		if(nPlot >= 0)
		{
			DataPlot dp = gl.DataPlots(nPlot);
			if(!dp)
				return -1;
			nBad = dp.UpdateThemeIDs(tr.Root);
			bOK = dp.ApplyFormat(tr, TRUE, TRUE);
		}
		else if(strObj.GetLength() > 0)
		{
			GraphObject go = gl.GraphObjects(strObj);
			if(!go)
				return -1;
			nBad = go.UpdateThemeIDs(tr.Root);
			bOK = go.ApplyFormat(tr, TRUE, TRUE);
		}
		else
		{
			nBad = gl.UpdateThemeIDs(tr.Root);
			bOK = gl.ApplyFormat(tr, TRUE, TRUE);
		}
	}
	if(nBad != 0)
		return 100 + nBad;
	return bOK ? 0 : -3;
}

// 当前 Origin 进程号：attach 后确认连的是自己启动的实例
int oc_pid()
{
	return GetCurrentProcessId();
}
