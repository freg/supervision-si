<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
* Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
* Contributors : -
*
* This file is part of ProjeQtOr.
*
* ProjeQtOr is free software: you can redistribute it and/or modify it under
* the terms of the GNU Affero General Public License as published by the Free
* Software Foundation, either version 3 of the License, or (at your option)
* any later version.
*
* ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
* WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
* FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for
* more details.
*
* You should have received a copy of the GNU Affero General Public License along with
* ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
*
* You can get complete code of ProjeQtOr, other resource, help and information
* about contributors at http://www.projeqtor.org
*
*** DO NOT REMOVE THIS NOTICE ************************************************/

function pq_trim($val, $charList=null) {
  $result = $val;
  if ($val!==null){
	  if ($charList !== null){
	    $result = trim($val, $charList);
	  }else{
	    $result = trim($val);
	  }
  }
  return $result;
}

function pq_rtrim($val,$charList=null){
  $result = $val;
  if ($val!==null){
  	if ($charList !== null){
  		$result = rtrim($val, $charList);
  	}else{
  		$result = rtrim($val);
  	}
  }
  return $result;
}

function pq_ltrim($val,$charList=null){
  $result = $val;
  if ($val!==null){
  	if ($charList !== null){
  		$result = ltrim($val, $charList);
  	}else{
  		$result = ltrim($val);
  	}
  }
  return $result;
}

function pq_substr($val,$start,$length=null) {
	$result = $val;
	if ($val!==null and $start!==null){
		if ($length !== null){
			$result = substr($val, $start, $length);
		}else{
			$result = substr($val, $start);
		}
	}
	return $result;
}

function pq_mb_substr($val,$start,$length=null,$encoding=null) {
	$result = $val;
	if ($val!==null and $start!==null){
		if ($length !== null  and !$encoding){
			$result = mb_substr($val, $start, $length);
		}else if($length !== null and $encoding !== null){
		    $result = mb_substr($val, $start, $length, $encoding);
		}else{
			$result = mb_substr($val, $start);
		}
	}
	return $result;
}

function pq_htmlspecialchars($val, $flags = null, $charset = null, $double_encode = null){
  $val=pq_remove_non_printable($val, true);
  $result = $val;
  if ($val!==null){
    if($flags !== null and $charset !== null and $double_encode !== null){
      $result=htmlspecialchars($val, $flags, $charset, $double_encode);
    }elseif($flags !== null and $charset !== null){
      $result=htmlspecialchars($val, $flags, $charset);
    }elseif($flags !== null){
      $result=htmlspecialchars($val, $flags);
    }else{
      $result=htmlspecialchars($val);
    }
  }
  return $result;
}

function pq_strlen($val){
  $result = 0;
  if ($val!==null){
	  $result = strlen($val);
  }
  return $result;
}

function pq_mb_strlen($val, $encoding=null){
	$result = 0;
	if ($val!==null){
	  if ($encoding !== null){
	  	$result = mb_strlen($val,$encoding);
	  }else{
	  	$result = mb_strlen($val);
	  }
	}
	return $result;
}

function pq_strtolower($val){
  $result = $val;
  if ($val!==null){
	$result = strtolower($val);
  }
  return $result;
}

function pq_mb_strtolower($val, $encoding=null){
	$result = $val;
	if ($val!==null){
		if ($encoding !== null){
			$result = mb_strtolower($val,$encoding);
		}else{
			$result = mb_strtolower($val);
		}
	}
	return $result;
}

function pq_strtoupper($val){
	$result = $val;
	if ($val!==null){
		$result = strtoupper($val);
	}
	return $result;
}

function pq_mb_strtoupper($val, $encoding=null){
	$result = $val;
	if ($val!==null){
		if ($encoding !== null){
			$result = mb_strtoupper($val,$encoding);
		}else{
			$result = mb_strtoupper($val);
		}
	}
	return $result;
}

function pq_str_replace($val, $replace, $subject, $count=null){
  $result = $subject;
  if ($val!==null and $replace!==null and $subject!==null){
    if ($count !== null){
    	$result = str_replace($val, $replace, $subject, $count);
    }else{
    	$result = str_replace($val, $replace, $subject);
    }
  }
  return $result;
}

function pq_substr_replace($val, $replace, $start, $length=null){
	$result = $val;
	if ($val!==null and $replace!==null and $start!==null){
		if ($length !== null){
			$result = substr_replace($val, $replace, $start, $length);
		}else{
			$result = substr_replace($val, $replace, $start);
		}
	}
	return $result;
}

function pq_strpos($val, $needle, $offset=null){
	$result = false;
	if (is_object($val) or is_array($val)) return false;
	if ($val!==null and $needle!==null){
		if ($offset !== null){
			$result = strpos($val, $needle, $offset);
		}else{
			$result = strpos($val, $needle);
		}
	}
	return $result;
}

function pq_mb_strpos($val, $needle, $offset=null, $encoding=null){
	$result = '';
	if ($val!==null and $needle!==null){
		if ($offset !== null and !$encoding){
			$result = mb_strpos($val, $needle, $offset);
		}else if ($offset !== null and $encoding !== null){
			$result = mb_strpos($val, $needle, $offset, $encoding);
		}else{
			$result = mb_strpos($val, $needle);
		}
	}
	return $result;
}

function pq_strftime($val, $timestamp=null){
  $result = '';
  if ($val!==null){
    switch ($val) {
      case '%B':
          $val = 'F';
          break;
      case '%b':
      	$val = 'M';
      	  break;
      case '%Y':
          $val = 'Y';
          break;
      case '%y':
      	$val = 'y';
      	break;
      case '%m':
          $val = 'm';
          break;
    }
  	if ($timestamp){
  		$result = date($val, $timestamp);
  	}else{
  		$result = date($val);
  	}
  }
  return $result;
}

function pq_nvl($value,$defaultValue='') {
  if ($value===null) return $defaultValue;
  else return $value;
}

function pq_stripos($val, $needle, $offset=null){
  $result = false;
  if ($val!==null and $needle!==null){
  	if ($offset !== null){
  		$result = stripos($val, $needle, $offset);
  	}else{
  		$result = stripos($val, $needle);
  	}
  }
  return $result;
}

function pq_htmlentities($val, $flags=null, $charset=null, $double_encode=null){
  $result = '';
  if ($val!==null){
  	if ($double_encode !== null and $charset !== null and $flags !== null){
  		$result = htmlentities($val, $flags, $charset, $double_encode);
  	}else if($charset !== null and $flags !== null){
		$result = htmlentities($val, $flags, $charset);
  	}else if ($flags !== null){
	    $result = htmlentities($val, $flags);
  	}else{
  	    $result = htmlentities($val);
  	}
  }
  return $result;
}

function pq_nl2br($val, $is_xhtml=null){
  $result = $val;
	if ($val!==null){
		if ($is_xhtml !== null){
			$result = nl2br($val,$is_xhtml);
		}else{
			$result = nl2br($val);
		}
	}
	return $result;
}

function pq_ucfirst($val) {
  if (! $val) return $val;
  else return ucfirst($val);
}

function pq_strtotime($time, $now = null) {
$result = $time;
	if ($time!==null){
		if ($now !== null){
			$result = strtotime($time,$now);
		}else{
			$result = strtotime($time);
		}
	}
	return $result;
}

function pq_explode($delimiter, $string, $limit=null){
  $result = array();
  if ($delimiter!==null and $string!==null){
    if ($limit !== null){
      $result = explode($delimiter, $string, $limit);
    }else{
      $result = explode($delimiter, $string);
    }
  }
  return $result;
}

function pq_utf8_encode($val) {
  //return utf8_encode($val) ; // Deprecated on PHP 8.2
  return mb_convert_encoding($val, 'UTF-8', 'ISO-8859-1');
}
function pq_utf8_decode($val) {
  //return utf8_decode($val) ; // Deprecated on PHP 8.2
  return mb_convert_encoding($val, 'ISO-8859-1','UTF-8');
}

function pq_mb_split($pattern, $string, $limit = -1) {
  if (! $string or ! $pattern) return $string;
  return mb_split($pattern, $string, $limit);
}

function pq_ord($val) {
  $result = $val;
  if ($val!==null and $val!==''){
    $result = ord($val);
  } else {
    $result = 0;
  }
  return $result;
}

function pq_remove_non_printable($string, $keepCRLF=false) {
  if (! $string or pq_trim($string)=='') return '';
  //if ($keepCRLF) return preg_replace('/[^\r\n[:print:]]/', '', $string);
  if ($keepCRLF) return preg_replace('/^\r\n[\x00-\x1F\x7F\xA0]/u', '', $string);
  return preg_replace('/[\x00-\x1F\x7F\xA0]/u', '', $string);
}
function pq_array_key_exists($string, $array) {
  if ($array===null or ! is_array($array)) return false;
  if ($string===null) return false;
  return array_key_exists($string, $array);
}

?>